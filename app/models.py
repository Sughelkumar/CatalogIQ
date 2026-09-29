from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

VALID_CATEGORIES = [
    "Groceries", "Beverages", "Personal Care", "Household",
    "Electronics", "Fashion", "Home & Kitchen", "Other"
]

class EnrichmentOutput(BaseModel):
    clean_title: str
    category: str
    brand: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class ProductInput(BaseModel):
    sku: str
    raw_title: str
    raw_description: Optional[str] = None

class JobCreateInput(BaseModel):
    products: List[ProductInput]

class ProductUpdateInput(BaseModel):
    clean_title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None