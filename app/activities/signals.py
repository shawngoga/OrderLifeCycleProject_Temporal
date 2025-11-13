import logging
from datetime import timedelta
from dataclasses import asdict
from temporalio import workflow
from temporalio.common import RetryPolicy
from app.activities.activities import (
    activity_cancel_order,
    activity_refund_payment,
    activity_update_address,
    activity_get_order_state,
)

FAST_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(milliseconds=100),
    backoff_coefficient=1.0,
    maximum_interval=timedelta(milliseconds=100),
)

class SignalManager:
    def __init__(self, workflow_instance, logger):
        self.logger = logger
        self.signal_queue = []
        self.new_address = None

    def queue_cancel(self):
        self.signal_queue.append(("cancel", None))

    def queue_update_address(self, new_address: dict):
        self.signal_queue.append(("update_address", new_address))
        self.new_address = new_address

    def has_pending(self) -> bool:
        return bool(self.signal_queue)

    async def process_signals(self, order, current_stage: str) -> str | None:
        result = None
        for signal_type, payload in self.signal_queue:
            if signal_type == "cancel":
                result = await self._handle_cancel(order, current_stage)
            elif signal_type == "update_address":
                await self._handle_address_update(order, payload, current_stage)
        self.signal_queue.clear()
        return result

    async def _handle_cancel(self, order, stage: str) -> str | None:
        order_id = order.order_id

        if stage in ["received", "validated", "reviewed"]:
            await workflow.execute_activity(
                activity_cancel_order,
                asdict(order),
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=FAST_RETRY_POLICY,
                task_queue="order-tq"
            )
            self.logger.info(f"[SignalManager] cancel success: {order_id} canceled before payment")
            return f"Order {order_id} canceled before payment."

        elif stage in ["charged", "package_prepared", "dispatched"]:
            await workflow.execute_activity(
                activity_cancel_order,
                asdict(order),
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=FAST_RETRY_POLICY,
                task_queue="order-tq"
            )
            await workflow.execute_activity(
                activity_refund_payment,
                args=(asdict(order), "cancel"),
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=FAST_RETRY_POLICY,
                task_queue="order-tq"
            )
            self.logger.info(f"[SignalManager] cancel success: {order_id} canceled after payment, refund issued")
            return f"Order {order_id} canceled after payment. Refund issued."

        elif stage in ["shipping", "shipped"]:
            self.logger.info(f"[SignalManager] cancel rejected: {order_id} already in stage '{stage}'")
            return {"status": f"[{order_id}] Cancel rejected, order already {stage} or workflow completed"}
        else:
            self.logger.warning(f"[SignalManager] cancel rejected: {order_id} :'{stage}'")
            return None

    async def _handle_address_update(self, order, new_address: dict, stage: str):
        order_id = order.order_id

        if stage in ["received", "validated", "reviewed", "charged", "package_prepared"]:
            order.address = new_address
            await workflow.execute_activity(
                activity_update_address,
                args=(asdict(order), new_address),
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=FAST_RETRY_POLICY,
                task_queue="order-tq"
            )
            self.logger.info(f"[SignalManager] address update success: {order_id} updated to {new_address}")
        elif stage in ["dispatched", "shipping", "shipped"]:
            self.logger.info(f"[SignalManager] address update rejected: {order_id} already in stage '{stage}'")
            return {
                "status": f"[{order_id}] Address update rejected, order already {stage} or workflow completed"
            }
        else:
            self.logger.warning(f"[SignalManager] address update rejected: {order_id} : '{stage}'")
            return {
                "status": f"[{order_id}] Address update rejected, invalid stage '{stage}'"
            }

