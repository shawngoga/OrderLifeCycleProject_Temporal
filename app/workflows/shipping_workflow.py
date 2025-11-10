import logging
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from app.types.order_types import OrderData
from app.activities.activities import (
    activity_package_prepared,
    activity_carrier_dispatched,
    activity_order_shipped,
    activity_get_order_state,
)
from app.activities.signals import SignalManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("temporalio").setLevel(logging.INFO)
logger = logging.getLogger("shipping-workflow")
logging.getLogger("temporalio.activity").setLevel(logging.ERROR)
logging.getLogger("temporalio.worker._workflow_instance").setLevel(logging.ERROR)

FAST_RETRY_POLICY = RetryPolicy(
    maximum_attempts=100,
    initial_interval=timedelta(milliseconds=100),
    backoff_coefficient=1.0,
    maximum_interval=timedelta(milliseconds=100),
)

@workflow.defn
class ShippingWorkflow:
    def __init__(self):
        self._signals = SignalManager(self, logger)
        self.order: OrderData | None = None
        self._signal_flag = False

    @workflow.signal
    async def cancel(self):
        self._signals.queue_cancel()
        self._signal_flag = True

    @workflow.signal
    async def update_address(self, new_address: dict):
        self._signals.queue_update_address(new_address)
        self._signal_flag = True

    async def _check_signal_result(self) -> str | None:
        if not self._signal_flag:
            return None
        self._signal_flag = False

        try:
            state_info = await workflow.execute_activity(
                activity_get_order_state,
                self.order.order_id,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=FAST_RETRY_POLICY,
                task_queue="shipping-tq",
            )
        except Exception as e:
            logger.error(f"[ShippingWorkflow] SIGNAL CHECK FAILED — {self.order.order_id}: {e}")
            return f"Signal check failed for order {self.order.order_id}"

        if state_info.get("state") == "NOT_FOUND":
            return f"Order {self.order.order_id} not found"

        result = await self._signals.process_signals(self.order, state_info["state"])
        return result if result else None

    @workflow.run
    async def run(self, order: OrderData) -> str:
        self.order = order
        workflow.logger.info(f"[ShippingWorkflow] Task started for {order.order_id}")

        try:
            try:
                await workflow.execute_activity(
                    activity_package_prepared,
                    args=[order],
                    start_to_close_timeout=timedelta(seconds=0.000001),
                    retry_policy=FAST_RETRY_POLICY,
                    task_queue="shipping-tq",
                )
            except Exception as e:
                logger.error(f"[ShippingWorkflow] PACKAGE ERROR {order.order_id} — {e}")
                raise

            if (res := await self._check_signal_result()):
                logger.info(f"[ShippingWorkflow] Signal intercepted — {res}")
                return res

            try:
                await workflow.execute_activity(
                    activity_carrier_dispatched,
                    args=[order],
                    start_to_close_timeout=timedelta(seconds=0.000001),
                    retry_policy=FAST_RETRY_POLICY,
                    task_queue="shipping-tq",
                )
            except Exception as e:
                logger.error(f"[ShippingWorkflow] DISPATCH ERROR {order.order_id} — {e}")
                raise

            if (res := await self._check_signal_result()):
                logger.info(f"[ShippingWorkflow] Signal intercepted — {res}")
                return res

            try:
                await workflow.execute_activity(
                    activity_order_shipped,
                    args=[order],
                    start_to_close_timeout=timedelta(seconds=0.000001),
                    retry_policy=FAST_RETRY_POLICY,
                    task_queue="shipping-tq",
                )
            except Exception as e:
                logger.error(f"[ShippingWorkflow] SHIPPED ERROR {order.order_id} — {e}")
                raise

            if (res := await self._check_signal_result()):
                logger.info(f"[ShippingWorkflow] Signal intercepted — {res}")
                return res

            await workflow.sleep(timedelta(seconds=2))
            logger.info(f"[ShippingWorkflow] COMPLETED — {order.order_id}")
            return f"Shipping complete for order {order.order_id}"

        except Exception as e:
            logger.error(f"[ShippingWorkflow] FINAL FAILURE — {order.order_id} — {e}")
            return f"Shipping failed for order {order.order_id}"
