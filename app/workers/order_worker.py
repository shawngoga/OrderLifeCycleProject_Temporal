import logging
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from app.workflows.order_workflow import OrderWorkflow
from app.activities.activities import (
    activity_order_received,
    activity_order_validated,
    activity_manual_review,
    activity_payment_charged,
    activity_order_shipped,
    activity_package_prepared,
    activity_carrier_dispatched,
    activity_cancel_order,
    activity_refund_payment,
    activity_update_address,
    activity_get_order_state,
)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("temporalio").setLevel(logging.INFO)
logging.getLogger("temporalio.activity").setLevel(logging.ERROR)
logging.getLogger("temporalio.worker._workflow_instance").setLevel(logging.ERROR)
logger = logging.getLogger("order-worker")

async def main():
    try:
        logger.info("Connecting to Temporal...")
        client = await Client.connect("localhost:7233")
        worker = Worker(
            client,
            task_queue="order-tq",
            workflows=[OrderWorkflow],
            activities=[
                activity_order_received,
                activity_order_validated,
                activity_manual_review,
                activity_payment_charged,
                activity_order_shipped,
                activity_package_prepared,
                activity_carrier_dispatched,
                activity_cancel_order,
                activity_refund_payment,
                activity_update_address,
                activity_get_order_state,
            ],
        )
        logger.info("Order worker running on task queue: order-tq")
        await worker.run()
    except Exception as e:
        logger.error(f"Order worker crashed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
