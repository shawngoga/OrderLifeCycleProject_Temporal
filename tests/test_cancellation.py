import asyncio
import random
from temporalio.client import Client
from app.workflows.order_workflow import OrderWorkflow, OrderData, Address, Item

async def main():
    try:
        print("Connecting to Temporal...")
        client = await Client.connect("localhost:7233")

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

        order = OrderData(
            order_id=f"test-order-{random.randint(1000,9999)}",
            address=address,
            items=items
        )

        print("Starting workflow...")
        handle = await client.start_workflow(
            OrderWorkflow.run,
            id=order.order_id,
            task_queue="order-tq",
            args=[order.order_id, address.__dict__, [item.__dict__ for item in items]],
        )

        print(f"Workflow started with ID: {handle.id}")

        # Wait random time before sending cancel signal
        delay = random.uniform(2, 6)
        print(f"Waiting {delay:.2f} seconds before sending cancel signal...")
        await asyncio.sleep(delay)

        # Send cancel signal
        await handle.signal(OrderWorkflow.cancel)
        print(f"Sent cancel signal to: {order.order_id}")

        # Wait for workflow to complete with timeout
        try:
            result = await asyncio.wait_for(handle.result(), timeout=30)
            print(f"Workflow result: {result}")
        except asyncio.TimeoutError:
            print(f"Timeout waiting for workflow {order.order_id} to complete.")

    except Exception as e:
        print(f"Failed to start workflow: {e}")

asyncio.run(main())
