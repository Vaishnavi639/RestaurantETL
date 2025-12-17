from pydantic import BaseModel, Field, root_validator
from typing import Optional, List, Any


class MenuItem(BaseModel):
    item_name: str
    variant: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None

    price: Optional[float] = None
    half_plate_price: Optional[float] = None
    full_plate_price: Optional[float] = None
    small_price: Optional[float] = None
    medium_price: Optional[float] = None
    large_price: Optional[float] = None

    price_display: Optional[str] = None

    def has_any_price(self) -> bool:
        return any([
            self.price is not None,
            self.half_plate_price is not None,
            self.full_plate_price is not None,
            self.small_price is not None,
            self.medium_price is not None,
            self.large_price is not None,
        ])


class MenuData(BaseModel):
    restaurant_name: str
    items: List[MenuItem]
    total_items: int
    extraction_metadata: Optional[dict] = None

    def to_dataframe(self):
        import pandas as pd
        rows = []
        for it in self.items:
            rows.append(it.dict())
        df = pd.DataFrame(rows)
        return df
