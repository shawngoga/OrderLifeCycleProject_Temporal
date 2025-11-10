from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

def utcnow():
    return datetime.utcnow()

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    state = Column(String, default="RECEIVED")
    address_json = Column(JSON)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"))
    status = Column(String)
    amount = Column(Float)
    created_at = Column(DateTime, default=utcnow)

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String)
    type = Column(String)
    payload_json = Column(JSON)
    ts = Column(DateTime, default=utcnow)
