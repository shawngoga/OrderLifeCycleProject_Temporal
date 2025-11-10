from dataclasses import dataclass
from typing import List

@dataclass
class Address:
    street: str
    city: str
    state: str
    zip: str

@dataclass
class Item:
    sku: str
    qty: int

@dataclass
class OrderData:
    order_id: str
    address: Address
    items: List[Item]
