import logging
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from app.activities.activities import (
    activity_get_order_state,
    activity_refund_payment,
)

FAST_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(milliseconds=100),
    backoff_coefficient=1.0,
    maximum_interval=timedelta(milliseconds=100),
)

@workflow.defn
class ReturnWorkflow:
    def __init__(self):
        self.logger = logging.getLogger("ReturnWorkflow")

    @workflow.run
    async def run(self, order_id: str):  # Accepts order_id directly
        self.logger.info(f"[ReturnWorkflow] started for order {order_id}")

        # Check current order state
        state_result = await workflow.execute_activity(
            activity_get_order_state,
            args=[order_id],
            start_to_close_timeout=timedelta(seconds=2),
            retry_policy=FAST_RETRY_POLICY,
            task_queue="order-tq"
        )
        current_state = state_result["state"]
        

        if current_state not in [ "shipped"]:
            self.logger.info(f"[ReturnWorkflow] return rejected: {order_id} not yet shipped ")
            return f"Return rejected: Order {order_id} not yet shipped"

    
        simulated_order = {
            "order_id": order_id,
            "amount": 0  
        }

        refund_result = await workflow.execute_activity(
            activity_refund_payment,
            args=[simulated_order, "return"],
            start_to_close_timeout=timedelta(seconds=2),
            retry_policy=FAST_RETRY_POLICY,
            task_queue="order-tq"
        )

        # Log the actual result instead of a fixed message
        self.logger.info(f"[ReturnWorkflow] {refund_result}")
        return refund_result    