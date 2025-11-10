import logging
import asyncio
from datetime import timedelta
from temporalio import activity
from app.types.order_types import OrderData
from app.stubs.function_stubs import (
    order_received as stub_order_received,
    order_validated as stub_order_validated,
    payment_charged as stub_payment_charged,
    order_shipped as stub_order_shipped,
    package_prepared as stub_package_prepared,
    carrier_dispatched as stub_carrier_dispatched,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("temporalio").setLevel(logging.INFO)
logger = logging.getLogger("activity")
logging.getLogger("temporalio.activity").setLevel(logging.INFO)
logging.getLogger("temporalio.worker._workflow_instance").setLevel(logging.ERROR)

FAST_RETRY_POLICY = {
    "initial_interval": timedelta(milliseconds=100),
    "backoff_coefficient": 1.0,
    "maximum_interval": timedelta(milliseconds=100),
}

def log_event(db, order_id: str, event_type: str, payload: dict = None, ts=None) -> None:
    from datetime import datetime
    from ..db.models import Event
    db.add(Event(
        order_id=order_id,
        type=event_type,
        payload_json=payload or {},
        ts=ts or datetime.utcnow()
    ))

@activity.defn
async def activity_order_received(order: "OrderData") -> dict:
    from datetime import datetime
    from ..db.session import SessionLocal
    from ..db.models import Order

    attempt = activity.info().attempt
    logger.info(f"[Activity] order_received attempt {attempt}: {order.order_id}")

    try:
        result = await asyncio.wait_for(stub_order_received(order.order_id), timeout=0.00000001)
    except asyncio.TimeoutError:
        logger.warning(f"[Activity] order_received timeout: {order.order_id}")
        raise
    except Exception as e:
        logger.error(f"[Activity] order_received error: {order.order_id} — {str(e)}")
        raise

    with SessionLocal() as db:
        db_order = db.query(Order).filter(Order.id == order.order_id).first()
        if db_order:
            db_order.address_json = {
                "street": order.address.street,
                "city": order.address.city,
                "state": order.address.state,
                "zip": order.address.zip,
            }
            db_order.updated_at = datetime.utcnow()
            log_event(db, order.order_id, "ADDRESS_SET", {
                "address": db_order.address_json,
                "items": [{"sku": item.sku, "qty": item.qty} for item in order.items],
            })
            db.commit()
            logger.info(f"[Activity] address_set: {order.order_id}")
    return result

@activity.defn
async def activity_order_validated(order: dict) -> None:
    attempt = activity.info().attempt
    logger.info(f"[Activity] order_validated attempt {attempt}: {order['order_id']}")

    try:
        await asyncio.wait_for(stub_order_validated(order), timeout=0.00000001)
    except asyncio.TimeoutError:
        logger.warning(f"[Activity] order_validated timeout: {order['order_id']}")
        raise
    except Exception as e:
        logger.error(f"[Activity] order_validated error: {order['order_id']} — {str(e)}")
        raise

@activity.defn
async def activity_manual_review(order: dict) -> None:
    logger.info(f"[Activity] manual_review started: {order['order_id']}")
    await asyncio.sleep(2)
    logger.info(f"[Activity] manual_review completed: {order['order_id']}")

@activity.defn
async def activity_payment_charged(order: dict, payment_id: str) -> dict:
    from ..db.session import SessionLocal
    attempt = activity.info().attempt
    logger.info(f"[Activity] payment_charged attempt {attempt}: {order['order_id']}")

    try:
        with SessionLocal() as db:
            result = await asyncio.wait_for(
                stub_payment_charged(order, payment_id, db),
                timeout=0.00000001
            )
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Activity] payment_charged timeout: {order['order_id']}")
        raise
    except Exception as e:
        logger.error(f"[Activity] payment_charged error: {order['order_id']} — {str(e)}")
        raise

@activity.defn
async def activity_package_prepared(order: dict) -> str:
    attempt = activity.info().attempt
    logger.info(f"[Activity] package_prepared attempt {attempt}: {order['order_id']}")
    try:
        return await stub_package_prepared(order)
    except Exception as e:
        logger.error(f"[Activity] package_prepared error: {order['order_id']} — {e}")
        raise

@activity.defn
async def activity_carrier_dispatched(order: dict) -> str:
    attempt = activity.info().attempt
    logger.info(f"[Activity] carrier_dispatched attempt {attempt}: {order['order_id']}")
    try:
        return await stub_carrier_dispatched(order)
    except Exception as e:
        logger.error(f"[Activity] carrier_dispatched error: {order['order_id']} — {e}")
        raise

@activity.defn
async def activity_order_shipped(order: dict) -> str:
    attempt = activity.info().attempt
    logger.info(f"[Activity] order_shipping attempt {attempt}: {order['order_id']}")
    try:
        return await stub_order_shipped(order)
    except Exception as e:
        logger.error(f"[Activity] order_shipping error: {order['order_id']} — {e}")
        raise

@activity.defn
async def activity_cancel_order(order: dict) -> str:
    from datetime import datetime
    from ..db.session import SessionLocal
    from ..db.models import Order

    with SessionLocal() as db:
        db_order = db.query(Order).filter(Order.id == order["order_id"]).first()
        if db_order:
            db_order.state = "canceled"
            db_order.updated_at = datetime.utcnow()
            log_event(db, order["order_id"], "ORDER_CANCELED")
            db.commit()
            logger.info(f"[Activity] cancel_order: {order['order_id']}")
            return f"Order {order['order_id']} marked as canceled"
        logger.warning(f"[Activity] cancel_order failed: {order['order_id']} not found")
        return f"Order {order['order_id']} not found"

@activity.defn
async def activity_refund_payment(order: dict, reason: str) -> str:
    from datetime import datetime
    import uuid
    from ..db.session import SessionLocal
    from ..db.models import Payment, Order

    with SessionLocal() as db:
        db_order = db.query(Order).filter(Order.id == order["order_id"]).first()
        if not db_order:
            logger.warning(f"[Activity] refund_payment failed: Order {order['order_id']} not found")
            return f"Order {order['order_id']} not found"

        if reason == "return":
            if (datetime.utcnow() - db_order.updated_at).total_seconds() > 300:
                logger.info(f"[Activity] refund_payment rejected: {order['order_id']} — updated too long ago")
                return f"Return rejected for order {order['order_id']} — shipped too long ago"

        original_payment = db.query(Payment).filter(Payment.order_id == order["order_id"]).first()
        if not original_payment:
            logger.warning(f"[Activity] refund_payment failed: No payment found for {order['order_id']}")
            return f"No payment found for order {order['order_id']}"

        refund_payment = Payment(
            payment_id=str(uuid.uuid4()),
            order_id=order["order_id"],
            status="REFUNDED",
            amount=-original_payment.amount,
            created_at=datetime.utcnow()
        )
        db.add(refund_payment)

        db_order.state = "refunded"
        db_order.updated_at = datetime.utcnow()

        log_event(db, order["order_id"], "PAYMENT_REFUNDED", {
            "original_payment_id": original_payment.payment_id,
            "refund_payment_id": refund_payment.payment_id,
            "amount": -original_payment.amount,
            "reason": reason
        })
        db.commit()
        logger.info(f"[Activity] refund_payment: {order['order_id']} — ${-original_payment.amount} due to {reason}")
        return f"Refund issued for order {order['order_id']} due to {reason}"

@activity.defn
async def activity_update_address(order: dict, new_address: dict) -> str:
    from datetime import datetime
    from ..db.session import SessionLocal
    from ..db.models import Order

    with SessionLocal() as db:
        db_order = db.query(Order).filter(Order.id == order["order_id"]).first()
        if db_order:
            db_order.address_json = new_address
            db_order.updated_at = datetime.utcnow()
            log_event(db, order["order_id"], "ADDRESS_UPDATED", {"new_address": new_address})
            db.commit()
            logger.info(f"[Activity] update_address: {order['order_id']}")
            return f"Address updated for order {order['order_id']}"
        logger.warning(f"[Activity] update_address failed: {order['order_id']} not found")
        return f"Order {order['order_id']} not found"


@activity.defn
async def activity_fetch_order(order_id: str) -> dict:
    db = SessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    return order.to_dict() if order else {}

@activity.defn
async def activity_get_order_state(order_id: str) -> dict:
    from datetime import datetime
    from ..db.session import SessionLocal
    from ..db.models import Order
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"state": "NOT_FOUND"}
        return {"state": order.state}
