import asyncio
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
            order_id="test-order-05-00011",
            address=address,
            items=items
        )

        print("Starting workflow...")
        handle = await client.start_workflow(
            OrderWorkflow.run,
            id="test-order-050-001",
            task_queue="order-tq",
            args=[order.order_id, address.__dict__, [item.__dict__ for item in items]],
        )

        print(f"Workflow started with ID: {handle.id}")
    except Exception as e:
        print(f"Failed to start workflow: {e}")

asyncio.run(main())
