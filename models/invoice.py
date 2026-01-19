"""
Invoice data models using Pydantic
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date
from enum import Enum


class DocumentType(str, Enum):
    TAX_INVOICE = "TAX_INVOICE"
    BILL_OF_SUPPLY = "BILL_OF_SUPPLY"
    CREDIT_NOTE = "CREDIT_NOTE"
    DEBIT_NOTE = "DEBIT_NOTE"


class LineItem(BaseModel):
    """Individual line item in invoice"""
    description: str
    hsn_sac: str
    quantity: float
    unit: str = "NOS"
    rate: float
    amount: float
    
    # Optional fields
    discount: Optional[float] = 0.0
    taxable_value: Optional[float] = None
    tax_rate: Optional[float] = None
    cgst: Optional[float] = 0.0
    sgst: Optional[float] = 0.0
    igst: Optional[float] = 0.0


class InvoiceData(BaseModel):
    """Complete invoice data structure"""

    # Document Information
    invoice_number: str
    invoice_date: date
    document_type: DocumentType = DocumentType.TAX_INVOICE

    # Seller Information
    seller_name: str
    seller_gstin: str
    seller_address: Optional[str] = None
    seller_state: Optional[str] = None
    seller_pan: Optional[str] = None

    # Buyer Information
    buyer_name: str
    buyer_gstin: str
    buyer_address: Optional[str] = None
    buyer_state: Optional[str] = None
    buyer_pan: Optional[str] = None

    # Financial Details
    line_items: List[LineItem]
    subtotal: float
    discount: Optional[float] = 0.0
    taxable_value: Optional[float] = None
    cgst_amount: Optional[float] = 0.0
    sgst_amount: Optional[float] = 0.0
    igst_amount: Optional[float] = 0.0
    cess: Optional[float] = 0.0
    total_tax: Optional[float] = None  # ✅ CHANGED: Now optional, will be validated by GST Agent
    total_amount: float

    # GST Specific
    place_of_supply: Optional[str] = None
    irn: Optional[str] = None
    irn_date: Optional[date] = None
    qr_code_present: Optional[bool] = False
    reverse_charge: Optional[bool] = False

    # TDS Information
    tds_applicable: Optional[bool] = False
    tds_section: Optional[str] = None
    tds_rate: Optional[float] = None
    tds_amount: Optional[float] = None

    # Additional Information
    po_reference: Optional[str] = None
    po_date: Optional[date] = None
    payment_terms: Optional[str] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None

    # Metadata
    extraction_confidence: Optional[float] = 1.0
    format_type: Optional[str] = "json"

    def is_interstate(self) -> bool:
        """Check if transaction is interstate"""
        if self.seller_state and self.buyer_state:
            return self.seller_state != self.buyer_state
        return False

    def is_high_value(self, threshold: float = 1000000) -> bool:
        """Check if invoice exceeds threshold"""
        return self.total_amount > threshold


class ExtractionResult(BaseModel):
    """Result of extraction process"""
    data: InvoiceData
    confidence: float
    format_type: str
    errors: List[str] = []
    warnings: List[str] = []