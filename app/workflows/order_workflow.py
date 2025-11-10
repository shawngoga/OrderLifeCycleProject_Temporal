import logging
from datetime import timedelta
from typing import Optional
from app.types.order_types import Address, Item, OrderData
from temporalio import workflow
from temporalio.common import RetryPolicy
from app.activities.activities import (
    activity_order_received,
    activity_order_validated,
    activity_manual_review,
    activity_payment_charged,
    activity_get_order_state,
)
from app.workflows.shipping_workflow import ShippingWorkflow
from app.activities.signals import SignalManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("temporalio").setLevel(logging.INFO)
logging.getLogger("temporalio.activity").setLevel(logging.ERROR)
logging.getLogger("temporalio.worker._workflow_instance").setLevel(logging.ERROR)
logger = logging.getLogger("order-worker")

FAST_RETRY_POLICY = RetryPolicy(
    maximum_attempts=100,
    initial_interval=timedelta(milliseconds=100),
    backoff_coefficient=1.0,
    maximum_interval=timedelta(milliseconds=100),
)

@workflow.defn
class OrderWorkflow:
    def __init__(self):
        self._signals = SignalManager(self, logger)
        self.order: Optional[OrderData] = None
        self._signal_flag = False
        self._signal_result: Optional[str] = None

    @workflow.signal
    async def cancel(self):
        self._signals.queue_cancel()
        self._signal_flag = True

    @workflow.signal
    async def update_address(self, new_address: dict):
        self._signals.queue_update_address(new_address)
        self._signal_flag = True

    async def check_signal_result(self) -> Optional[str]:
        if not self._signal_flag:
            return None
        self._signal_flag = False

        try:
            state_info = await workflow.execute_activity(
                activity_get_order_state,
                self.order.order_id,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=FAST_RETRY_POLICY,
                task_queue="order-tq"
            )
        except Exception as e:
            logger.error(f"[OrderWorkflow] SIGNAL CHECK FAILED — {self.order.order_id}: {e}")
            return f"Signal check failed for order {self.order.order_id}"

        if state_info["state"] == "NOT_FOUND":
            return f"Order {self.order.order_id} not found"

        return await self._signals.process_signals(self.order, state_info["state"])

    @workflow.run
    async def run(self, order_id: str, address: dict, items: list) -> str:
        self.order = OrderData(
            order_id=order_id,
            address=Address(**address),
            items=[Item(**item) for item in items]
        )

        await workflow.sleep(0.001)

        try:
            await workflow.execute_activity(
                activity_order_received,
                args=[self.order],
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=FAST_RETRY_POLICY,
            )
        except Exception as e:
            logger.error(f"[OrderWorkflow] RECEIVED ERROR {order_id} — {e}")
            raise

        if result := await self.check_signal_result():
            return result

        try:
            await workflow.execute_activity(
                activity_order_validated,
                args=[self.order],
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=FAST_RETRY_POLICY,
            )
        except Exception as e:
            logger.error(f"[OrderWorkflow] VALIDATED ERROR {order_id} — {e}")
            raise

        if result := await self.check_signal_result():
            return result

        await workflow.sleep(0.001)

        await workflow.execute_activity(
            activity_manual_review,
            args=[self.order],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=FAST_RETRY_POLICY,
        )

        if result := await self.check_signal_result():
            return result

        try:
            await workflow.execute_activity(
                activity_payment_charged,
                args=[self.order, f"payment-{order_id}"],
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=FAST_RETRY_POLICY,
            )
        except Exception as e:
            logger.error(f"[OrderWorkflow] PAYMENT ERROR {order_id} — {e}")
            raise

        if result := await self.check_signal_result():
            return result

        self.order.workflow_ref = self

        await workflow.execute_child_workflow(
            ShippingWorkflow.run,
            self.order,
            id=f"shipping-{order_id}",
            task_queue="shipping-tq",
        )

        if result := await self.check_signal_result():
            return result

        logger.info(f"[OrderWorkflow] COMPLETED — {order_id}")
        return f"Order {order_id} completed"
