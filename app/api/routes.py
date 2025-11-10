from pydantic import BaseModel
from typing import List, Dict, Optional

class OrderRequest(BaseModel):
    order_id: str
    items: List[Dict]
    address: Dict
    amount: Optional[float] = None