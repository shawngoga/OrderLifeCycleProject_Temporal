import logging
logger = logging.getLogger("main")

from datetime import timedelta
from fastapi import FastAPI, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from temporalio.client import Client , WorkflowExecutionStatus
import subprocess, asyncio, socket, os, random
from pydantic import BaseModel
from typing import List
from app.workflows import OrderWorkflow, ReturnWorkflow
from app.db.session import SessionLocal
from app.db.models import Order, Payment, Event
from tabulate import tabulate
from app.activities.activities import activity_get_order_state

app = FastAPI()
app.state.client = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def wait_for_temporal(host="localhost", port=7233, timeout=30):
    for i in range(timeout):
        try:
            with socket.create_connection((host, port), timeout=1):
                logger.info(f"Temporal server is ready (attempt {i+1})")
                return True
        except OSError:
            await asyncio.sleep(1)
    return False

@app.post("/start-server", tags=["System"])
async def start_temporal_and_workers():
    try:
        temporal_path = os.path.expanduser("~\\.temporal\\temporal.exe")

        logger.info("Launching Temporal server...")
        subprocess.Popen([
            "powershell", "-Command",
            f"Start-Process -FilePath \"{temporal_path}\" -ArgumentList 'server start-dev' -WindowStyle Normal"
        ])

        logger.info("Waiting for Temporal server to be ready...")
        ready = await wait_for_temporal()
        if not ready:
            raise HTTPException(status_code=503, detail="Temporal server did not start in time")

        logger.info("Connecting Temporal client...")
        app.state.client = await Client.connect("localhost:7233")
        logger.info("Temporal client connected.")

        logger.info("Launching workers...")
        for worker_script in ["order_worker", "shipping_worker", "returns_worker"]:
            subprocess.Popen([
                "powershell", "-Command",
                f"Start-Process powershell -WindowStyle Normal -ArgumentList 'cd \"{os.getcwd()}\"; .\\.venv\\Scripts\\Activate.ps1; python -m app.workers.{worker_script}; Read-Host'"
            ])
            logger.info(f"{worker_script} launched")

        return {"status": "Temporal server and workers started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Startup failed: {str(e)}")


def require_temporal():
    if app.state.client is None:
        raise HTTPException(status_code=503, detail="Temporal client not connected. Call /start-server first.")
    return app.state.client

class AddressInput(BaseModel):
    street: str
    city: str
    state: str
    zip: str

class ItemInput(BaseModel):
    sku: str
    qty: int

class OrderInput(BaseModel):
    address: AddressInput
    items: List[ItemInput]

def generate_order_id(db: Session):
    count = db.query(Order).count()
    return f"order-{count + 1}"

@app.post("/start-order", tags=["Workflow"])
async def start_order(order: OrderInput, db: Session = Depends(get_db)):
    client = require_temporal()
    order_id = generate_order_id(db)
    address_dict = order.address.dict()
    items_list = [item.dict() for item in order.items]

    handle = await client.start_workflow(
        OrderWorkflow.run,
        id=order_id,
        task_queue="order-tq",
        args=[order_id, address_dict, items_list]
    )
    logger.info(f"[{order_id}] Workflow started")
    return {"workflow_id": order_id}

@app.post("/update-address", tags=["Workflow"])
async def update_address(order_id: str = Body(...), new_address: AddressInput = Body(...)):
    client = require_temporal()
    handle = client.get_workflow_handle(order_id)

    # Check workflow execution status
    desc = await handle.describe()
    if desc.status in [
        WorkflowExecutionStatus.COMPLETED,
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.TIMED_OUT,
        WorkflowExecutionStatus.TERMINATED,
    ]:
        logger.info(f"[{order_id}] Address update rejected — workflow already finished")
        return {"status": f"[{order_id}] Address update rejected, order already shipped or workflow completed"}

    # Send signal
    await handle.signal(OrderWorkflow.update_address, new_address.dict())
    logger.info(f"[{order_id}] Address update signal sent")

    # Check current stage
    try:
        state = await activity_get_order_state(order_id)
        stage = state["state"]

        if stage in ["dispatched", "shipping", "shipped"]:
            logger.info(f"[{order_id}] Address update rejected — stage is '{stage}'")
            return {"status": f"[{order_id}] Address update signal sent, but rejected due to stage: '{stage}'"}
        else:
            logger.info(f"[{order_id}] Address update accepted — stage is '{stage}'")
            return {"status": f"[{order_id}] Address update signal sent and accepted at stage: '{stage}'"}

    except Exception as e:
        logger.warning(f"[{order_id}] Could not fetch stage after address update: {str(e)}")
        return {"status": f"[{order_id}] Address update signal sent, but stage could not be verified"}



@app.post("/cancel-order", tags=["Workflow"])
async def cancel_order(order_id: str = Body(...)):
    client = require_temporal()
    handle = client.get_workflow_handle(order_id)
    
    desc = await handle.describe()
    if desc.status in [
        WorkflowExecutionStatus.COMPLETED,
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.TIMED_OUT,
        WorkflowExecutionStatus.TERMINATED,
    ]:
        logger.info(f"[{order_id}] Cancel rejected — workflow already finished")
        return {"status": f"[{order_id}] Cancel rejected, order already shipped or workflow completed"}

    # Send signal
    await handle.signal(OrderWorkflow.cancel)
    logger.info(f"[{order_id}] Cancel signal sent")

    # Check current stage
    try:
        state = await activity_get_order_state(order_id)
        stage = state["state"]

        if stage in ["shipping", "shipped", "package_prepared", "dispatched"]:
            logger.info(f"[{order_id}] Cancel signal rejected — stage is '{stage}'")
            return {"status": f"[{order_id}] Cancel signal sent, but rejected due to stage: '{stage}'"}
        else:
            logger.info(f"[{order_id}] Cancel signal accepted — stage is '{stage}'")
            return {"status": f"[{order_id}] Cancel signal sent and accepted at stage: '{stage}'"}

    except Exception as e:
        logger.warning(f"[{order_id}] Could not fetch stage after cancel signal: {str(e)}")
        return {"status": f"[{order_id}] Cancel signal sent, but stage could not be verified"}

@app.post("/return-order", tags=["Workflow"])
async def start_return(order_id: str):
    client = require_temporal()
    handle = await client.start_workflow(
        ReturnWorkflow.run,
        id=f"return-{order_id}",
        task_queue="returns-tq",
        args=[order_id],
    )
    return {"return_workflow_id": handle.id}

@app.get("/get-order-stage", tags=["Workflow"])
async def get_stage(order_id: str):
    try:
        result = await activity_get_order_state(order_id)  # direct function call
        return {"order_id": order_id, "stage": result["state"]}
    except Exception as e:
        logger.error(f"[{order_id}] Failed to get stage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stage for order {order_id}")


@app.get("/db-dump", tags=["Database"])
async def db_dump(db: Session = Depends(get_db)):
    orders = db.query(Order).all()
    payments = db.query(Payment).all()
    events = db.query(Event).all()

    def print_table(title, rows, headers):
        print(f"\n🔹 {title}")
        print(tabulate(rows, headers=headers, tablefmt="grid"))

    print_table("Events", [
        [e.id, e.order_id, e.type, str(e.payload_json), e.ts.isoformat()] for e in events
    ], ["ID", "Order ID", "Type", "Payload", "Timestamp"])

    print_table("Payments", [
        [p.payment_id, p.order_id, p.status, p.amount, p.created_at.isoformat()] for p in payments
    ], ["Payment ID", "Order ID", "Status", "Amount", "Created At"])

    print_table("Orders", [
        [o.id, o.state, str(o.address_json), o.created_at.isoformat(), o.updated_at.isoformat()] for o in orders
    ], ["Order ID", "State", "Address", "Created At", "Updated At"])

    return {"status": "DB dump printed to terminal"}

@app.post("/test-cancel-order", tags=["Test"])
async def test_cancel_order():
    client = require_temporal()
    order_id = f"Test-{random.randint(1000,9999)}"
    address = {"street": "123 Test St", "city": "Nashville", "state": "TS", "zip": "00000"}
    items = [{"sku": "test-item", "qty": 1}]
    handle = await client.start_workflow(
        OrderWorkflow.run,
        id=order_id,
        task_queue="order-tq",
        args=[order_id, address, items],
    )
    delay = random.randint(1, 15)
    asyncio.create_task(delayed_signal_cancel(handle, delay))
    return {"workflow_id": order_id, "cancel_delay_seconds": delay}

async def delayed_signal_cancel(handle, delay: int):
    await asyncio.sleep(delay)
    await handle.signal(OrderWorkflow.cancel)

@app.post("/test-update-address", tags=["Test"])
async def test_update_address():
    client = require_temporal()
    order_id = f"Test-{random.randint(1000,9999)}"
    address = {"street": "123 Test St", "city": "Nashville", "state": "TS", "zip": "00000"}
    items = [{"sku": "test-item", "qty": 1}]
    new_address = {"street": "456 Updated Ave", "city": "Newtown", "state": "NT", "zip": "99999"}
    handle = await client.start_workflow(
        OrderWorkflow.run,
        id=order_id,
        task_queue="order-tq",
        args=[order_id, address, items],
    )
    delay = random.randint(1, 15)
    asyncio.create_task(delayed_signal_update(handle, new_address, delay))
    return {"workflow_id": order_id, "update_delay_seconds": delay}

async def delayed_signal_update(handle, new_address: dict, delay: int):
    await asyncio.sleep(delay)
    await handle.signal(OrderWorkflow.update_address, new_address)

@app.get("/", tags=["System"])
async def root():
    return {"status": "ok"}
