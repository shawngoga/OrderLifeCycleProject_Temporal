import logging

logging.basicConfig(
    level=logging.INFO,  # Show both INFO and ERROR logs
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logging.getLogger("temporalio").setLevel(logging.INFO)
logger = logging.getLogger("shipping-worker")
logging.getLogger("temporalio.activity").setLevel(logging.ERROR)
logging.getLogger("temporalio.worker._workflow_instance").setLevel(logging.ERROR)


import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from app.workflows.shipping_workflow import ShippingWorkflow
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

async def main():
    try:
        logger.info("Connecting to Temporal...")
        client = await Client.connect("localhost:7233")
        worker = Worker(
            client,
            task_queue="shipping-tq",
            workflows=[ShippingWorkflow],
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
            max_concurrent_activities=100,
            max_concurrent_workflow_tasks=10,
        )
        logger.info("Shipping worker running on task queue: shipping-tq")
        await worker.run()
    except Exception as e:
        logger.error(f"Shipping worker crashed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
