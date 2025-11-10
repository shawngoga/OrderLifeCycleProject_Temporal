from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Order, Payment, Event
from tabulate import tabulate

engine = create_engine("sqlite:///orders.db")
Session = sessionmaker(bind=engine)
session = Session()

def show_table(title, rows, headers):
    print(f"\n🔹 {title}")
    print(tabulate(rows, headers=headers, tablefmt="grid"))

def show_orders():
    orders = session.query(Order).all()
    rows = [(
        o.id,
        o.state,
        o.address_json,
        o.created_at.isoformat() if o.created_at else None,
        o.updated_at.isoformat() if o.updated_at else None
    ) for o in orders]
    headers = ["Order ID", "State", "Address", "Created At", "Updated At"]
    show_table("Orders", rows, headers)

def show_payments():
    payments = session.query(Payment).all()
    rows = [(
        p.payment_id,
        p.order_id,
        p.status,
        p.amount,
        p.created_at.isoformat() if p.created_at else None
    ) for p in payments]
    headers = ["Payment ID", "Order ID", "Status", "Amount", "Created At"]
    show_table("Payments", rows, headers)

def show_events():
    events = session.query(Event).all()
    rows = [(
        e.id,
        e.order_id,
        e.type,
        e.payload_json,
        e.ts.isoformat() if e.ts else None
    ) for e in events]
    headers = ["Event ID", "Order ID", "Type", "Payload", "Timestamp"]
    show_table("Events", rows, headers)

if __name__ == "__main__":
    show_payments()
    show_events()
    show_orders()