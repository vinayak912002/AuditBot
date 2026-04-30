from pydantic import BaseModel, Field
from typing import Optional

class InvoiceData(BaseModel):
    """
    Standardized schema for extracted invoice data.
    Ensures all AI models return consistent, predictable keys.
    """
    Vendor: str = Field(description="Name of the vendor or company on the invoice")
    Date: str = Field(description="Date of the invoice (YYYY-MM-DD preferred)")
    Amount: float = Field(description="Total numeric amount of the invoice")
    Tax: Optional[float] = Field(default=0.0, description="Tax amount applied, if any")