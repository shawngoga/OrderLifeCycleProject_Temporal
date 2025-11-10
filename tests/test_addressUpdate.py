import asyncio
import logging
import random
from datetime import datetime
from temporalio.client import Client
from app.workflows.order_workflow import OrderWorkflow, OrderData, Address, Item

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

async def run():
    client = await Client.connect("localhost:7233")
    order_id = f"test-order-{int(datetime.utcnow().timestamp())}"
    logger.info(f"Starting workflow with ID: {order_id}")

    # Construct dataclass inputs
    address = Address(
        street="123 Main St",
        city="Boston",
        state="MA",
        zip="02118"
    )
    items = [
        Item(sku="Widget A", qty=2),
        Item(sku="Widget B", qty=1)
    ]

    # Start workflow with unpacked dicts
    handle = await client.start_workflow(
        OrderWorkflow.run,
        args=[order_id, address.__dict__, [item.__dict__ for item in items]],
        id=order_id,
        task_queue="order-tq"
    )

    logger.info(f"Workflow started with ID: {handle.id}")

    # Define staged address updates
    async def send_update(delay, label):
        await asyncio.sleep(delay)
        new_address = {
            "street": f"{label} Elm St",
            "city": "Boston",
            "state": "MA",
            "zip": "02118"
        }
        await handle.signal(OrderWorkflow.update_address, new_address)
        logger.info(f"[{label}] Sent address update signal")

    # Schedule updates at different stages
    await asyncio.gather(
        send_update(1.5, "early"),     # likely during 'received'
        send_update(3.5, "mid"),       # likely during 'reviewed' or 'charged'
        send_update(6.5, "late")       # likely during 'dispatched'
    )

    # Wait for workflow to complete
    try:
        result = await asyncio.wait_for(handle.result(), timeout=30)
        logger.info(f"Workflow completed: {result}")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout waiting for workflow {order_id} to complete.")

if __name__ == "__main__":
    asyncio.run(run())
