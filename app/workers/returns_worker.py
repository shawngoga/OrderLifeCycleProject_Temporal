import logging
logging.basicConfig(
    level=logging.INFO,  # <-- changed from ERROR to INFO
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("temporalio").setLevel(logging.INFO)  
logger = logging.getLogger("returns-worker")
logging.getLogger("temporalio.activity").setLevel(logging.ERROR)
logging.getLogger("temporalio.worker._workflow_instance").setLevel(logging.ERROR)
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from app.workflows.return_workflow import ReturnWorkflow
from app.activities.activities import activity_refund_payment
from app.activities.activities import activity_get_order_state

async def main():
    try:
        logger.info("Connecting to Temporal...")
        client = await Client.connect("localhost:7233")
        worker = Worker(
            client,
            task_queue="returns-tq",
            workflows=[ReturnWorkflow],
            activities=[activity_refund_payment, activity_get_order_state],
        )
        logger.info("Returns worker running on task queue: returns-tq")
        await worker.run()
    except Exception as e:
        logger.error(f"Returns worker crashed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
