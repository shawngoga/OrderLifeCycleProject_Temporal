import logging
import asyncio
from typing import Dict, Any
from ..db.models import Order, Payment, Event
from ..db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("temporalio").setLevel(logging.INFO)
logging.getLogger("temporalio.activity").setLevel(logging.ERROR)
logging.getLogger("temporalio.worker._workflow_instance").setLevel(logging.ERROR)
logger = logging.getLogger("stub")



async def flaky_call() -> None:
    import random
    rand_num = random.random()
    if rand_num < 0.02:
        raise RuntimeError("Forced failure for testing")
    if rand_num < 0.67:
        await asyncio.sleep(300)

# app/stubs/function_stubs.py (showing only updated bodies for relevant stubs)

import asyncio
from typing import Dict, Any
from app.activities.hedge_state import hedge_id_map, elect_hedge_winner

async def order_received(order_id: str) -> Dict[str, Any]:
    hedge_id = hedge_id_map.get(asyncio.current_task())
    try:
        
        await flaky_call()
        if not await elect_hedge_winner(hedge_id, order_id, logger):
            return {"order_id": order_id, "items": []}

        from datetime import datetime
        with SessionLocal() as db:
            existing = db.query(Order).filter(Order.id == order_id).first()
            if existing:
                raise ValueError("Order already exists")

            new_order = Order(
                id=order_id,
                state="received",
                address_json={"street": "123 Main St"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_order)
            db.add(Event(
                order_id=order_id,
                type="ORDER_RECEIVED",
                payload_json={"address": new_order.address_json},
                ts=datetime.utcnow()
            ))
            db.commit()

        logger.info(f"[Stub] order_received hedge {hedge_id} succeeded for {order_id}")
        return {"order_id": order_id, "items": [{"sku": "ABC", "qty": 1}]}
    except asyncio.CancelledError:
        logger.info(f"[Hedge] hedge {hedge_id} canceled during execution for order {order_id}")
        raise
    except Exception as e:
        logger.error(f"[Stub] order_received hedge {hedge_id} error: {order_id} — {str(e)}")
        raise


async def order_validated(order: Dict[str, Any]) -> bool:
    hedge_id = hedge_id_map.get(asyncio.current_task())
    try:
        logger.info(f"[Stub] order_validated hedge {hedge_id}: flaky_call starting")
        await flaky_call()
        logger.info(f"[Stub] order_validated hedge {hedge_id}: flaky_call completed")

        if not await elect_hedge_winner(hedge_id, order["order_id"], logger):
            return False

        from datetime import datetime
        with SessionLocal() as db:
            db_order = db.query(Order).filter(Order.id == order["order_id"]).first()
            if not db_order:
                raise ValueError("Order not found")

            db_order.state = "validated"
            db_order.updated_at = datetime.utcnow()
            db.add(Event(
                order_id=db_order.id,
                type="ORDER_VALIDATED",
                payload_json={"items": order.get("items", [])},
                ts=datetime.utcnow()
            ))
            db.commit()

        if not order.get("items"):
            raise ValueError("No items to validate")

        logger.info(f"[Stub] order_validated hedge {hedge_id} succeeded: {order['order_id']}")
        return True
    except asyncio.CancelledError:
        logger.info(f"[Hedge] hedge {hedge_id} canceled during execution for order {order['order_id']}")
        raise
    except Exception as e:
        logger.error(f"[Stub] order_validated hedge {hedge_id} error: {order['order_id']} — {str(e)}")
        raise


async def payment_charged(order: Dict[str, Any], payment_id: str, db) -> Dict[str, Any]:
    hedge_id = hedge_id_map.get(asyncio.current_task())
    try:
        logger.info(f"[Stub] payment_charged hedge {hedge_id}: flaky_call starting")
        await flaky_call()
        logger.info(f"[Stub] payment_charged hedge {hedge_id}: flaky_call completed")

        if not await elect_hedge_winner(hedge_id, order["order_id"], logger):
            return {"status": "canceled", "amount": 0}

        from datetime import datetime
        import random
        existing_payments = db.query(Payment).filter(Payment.order_id == order["order_id"]).all()
        if existing_payments:
            raise ValueError("Payment already exists")

        amount = random.randint(1, 9999)
        new_payment = Payment(
            payment_id=payment_id,
            order_id=order["order_id"],
            status="SUCCESSFUL",
            amount=amount,
            created_at=datetime.utcnow()
        )
        db.add(new_payment)

        db_order = db.query(Order).filter(Order.id == order["order_id"]).first()
        if db_order:
            db_order.state = "charged"
            db_order.updated_at = datetime.utcnow()

        db.add(Event(
            order_id=order["order_id"],
            type="PAYMENT_CHARGED",
            payload_json={"payment_id": payment_id, "amount": amount},
            ts=datetime.utcnow()
        ))
        db.commit()

        logger.info(f"[Stub] payment_charged hedge {hedge_id} succeeded: {order['order_id']} — ${amount}")
        return {"status": "charged", "amount": amount}
    except asyncio.CancelledError:
        logger.info(f"[Hedge] hedge {hedge_id} canceled during execution for order {order['order_id']}")
        raise
    except Exception as e:
        logger.error(f"[Stub] payment_charged hedge {hedge_id} error: {order['order_id']} — {str(e)}")
        raise

async def order_shipped(order: Dict[str, Any]) -> str:
    hedge_id = hedge_id_map.get(asyncio.current_task())
    try:
        logger.info(f"[Stub] order_shipped hedge {hedge_id}: flaky_call starting")
        await flaky_call()
        logger.info(f"[Stub] order_shipped hedge {hedge_id}: flaky_call completed")

        if not await elect_hedge_winner(hedge_id, order["order_id"], logger):
            # loser sentinel consistent with earlier stubs
            return ""  

        from datetime import datetime
        with SessionLocal() as db:
            db_order = db.query(Order).filter(Order.id == order["order_id"]).first()
            if not db_order:
                raise ValueError("Order not found")

            db_order.state = "shipped"
            db_order.updated_at = datetime.utcnow()
            db.add(Event(
                order_id=db_order.id,
                type="ORDER_SHIPPED",
                payload_json={},
                ts=datetime.utcnow()
            ))
            db.commit()

        logger.info(f"[Stub] order_shipped hedge {hedge_id} succeeded: {order['order_id']}")
        return "Shipped"
    except asyncio.CancelledError:
        logger.info(f"[Hedge] hedge {hedge_id} canceled during execution for order {order['order_id']}")
        raise
    except Exception as e:
        logger.error(f"[Stub] order_shipped hedge {hedge_id} error: {order['order_id']} — {str(e)}")
        raise


async def package_prepared(order: Dict[str, Any]) -> str:
    hedge_id = hedge_id_map.get(asyncio.current_task())
    try:
        logger.info(f"[Stub] package_prepared hedge {hedge_id}: flaky_call starting")
        await flaky_call()
        logger.info(f"[Stub] package_prepared hedge {hedge_id}: flaky_call completed")

        if not await elect_hedge_winner(hedge_id, order["order_id"], logger):
            return ""  

        from datetime import datetime
        with SessionLocal() as db:
            db_order = db.query(Order).filter(Order.id == order["order_id"]).first()
            if not db_order:
                raise ValueError("Order not found")

            db_order.state = "package_prepared"
            db_order.updated_at = datetime.utcnow()
            db.add(Event(
                order_id=db_order.id,
                type="PACKAGE_PREPARED",
                payload_json={},
                ts=datetime.utcnow()
            ))
            db.commit()

        logger.info(f"[Stub] package_prepared hedge {hedge_id} succeeded: {order['order_id']}")
        return "Package ready"
    except asyncio.CancelledError:
        logger.info(f"[Hedge] hedge {hedge_id} canceled during execution for order {order['order_id']}")
        raise
    except Exception as e:
        logger.error(f"[Stub] package_prepared hedge {hedge_id} error: {order['order_id']} — {str(e)}")
        raise


async def carrier_dispatched(order: Dict[str, Any]) -> str:
    hedge_id = hedge_id_map.get(asyncio.current_task())
    try:
        logger.info(f"[Stub] carrier_dispatched hedge {hedge_id}: flaky_call starting")
        await flaky_call()
        logger.info(f"[Stub] carrier_dispatched hedge {hedge_id}: flaky_call completed")

        if not await elect_hedge_winner(hedge_id, order["order_id"], logger):
            return ""  

        from datetime import datetime
        with SessionLocal() as db:
            db_order = db.query(Order).filter(Order.id == order["order_id"]).first()
            if not db_order:
                raise ValueError("Order not found")

            db_order.state = "dispatched"
            db_order.updated_at = datetime.utcnow()
            db.add(Event(
                order_id=db_order.id,
                type="CARRIER_DISPATCHED",
                payload_json={},
                ts=datetime.utcnow()
            ))
            db.commit()

        logger.info(f"[Stub] carrier_dispatched hedge {hedge_id} succeeded: {order['order_id']}")
        return "Dispatched"
    except asyncio.CancelledError:
        logger.info(f"[Hedge] hedge {hedge_id} canceled during execution for order {order['order_id']}")
        raise
    except Exception as e:
        logger.error(f"[Stub] carrier_dispatched hedge {hedge_id} error: {order['order_id']} — {str(e)}")
        raise
