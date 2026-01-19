"""
Simple arithmetic validator (Category C)
This is a starter implementation to test the system
"""

from models.invoice import InvoiceData
from models.validation import CheckResult, CategoryResult, CheckStatus, Severity


class ArithmeticValidator:
    """
    Category C: Arithmetic & Calculation Validation (10 checks)
    Starter implementation with basic checks
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    async def validate(self, invoice_data: InvoiceData, state=None) -> CategoryResult:
        """Execute arithmetic validation checks"""
        
        checks = []
        
        # C1: Line item quantity x rate = amount
        checks.append(await self._check_c1_line_item_amounts(invoice_data))
        
        # C2: Subtotal matches sum of line items
        checks.append(await self._check_c2_subtotal(invoice_data))
        
        # C3: Tax calculation accuracy
        checks.append(await self._check_c3_tax_calculation(invoice_data))
        
        # C10: Total amount
        checks.append(await self._check_c10_total_amount(invoice_data))
        
        return CategoryResult(
            category='C',
            category_name='Arithmetic & Calculation',
            checks=checks
        )
    
    async def _check_c1_line_item_amounts(self, invoice_data: InvoiceData) -> CheckResult:
        """C1: Line item quantity x rate = amount"""
        
        errors = []
        
        for idx, item in enumerate(invoice_data.line_items, 1):
            expected = item.quantity * item.rate
            if abs(item.amount - expected) > 1.0:  # ₹1 tolerance
                errors.append(
                    f"Line {idx}: Expected ₹{expected:.2f}, got ₹{item.amount:.2f}"
                )
        
        if not errors:
            return CheckResult(
                check_id='C1',
                check_name='Line Item Amount Calculation',
                status=CheckStatus.PASS,
                confidence=1.0,
                reasoning='All line item amounts calculated correctly',
                severity=Severity.MEDIUM
            )
        else:
            return CheckResult(
                check_id='C1',
                check_name='Line Item Amount Calculation',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning='; '.join(errors),
                severity=Severity.HIGH
            )
    
    async def _check_c2_subtotal(self, invoice_data: InvoiceData) -> CheckResult:
        """C2: Subtotal matches sum of line items"""
        
        calculated_subtotal = sum(item.amount for item in invoice_data.line_items)
        
        if abs(calculated_subtotal - invoice_data.subtotal) <= 1.0:
            return CheckResult(
                check_id='C2',
                check_name='Subtotal Matches Line Items',
                status=CheckStatus.PASS,
                confidence=1.0,
                reasoning=f'Subtotal ₹{invoice_data.subtotal:.2f} matches sum of line items',
                severity=Severity.MEDIUM
            )
        else:
            return CheckResult(
                check_id='C2',
                check_name='Subtotal Matches Line Items',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Subtotal mismatch: Expected ₹{calculated_subtotal:.2f}, got ₹{invoice_data.subtotal:.2f}',
                severity=Severity.HIGH
            )
    
    async def _check_c3_tax_calculation(self, invoice_data: InvoiceData) -> CheckResult:
        """C3: Tax calculation accuracy"""
        
        calculated_tax = (invoice_data.cgst_amount or 0) + \
                        (invoice_data.sgst_amount or 0) + \
                        (invoice_data.igst_amount or 0) + \
                        (invoice_data.cess or 0)
        
        if abs(calculated_tax - invoice_data.total_tax) <= 1.0:
            return CheckResult(
                check_id='C3',
                check_name='Tax Calculation Accuracy',
                status=CheckStatus.PASS,
                confidence=1.0,
                reasoning=f'Total tax ₹{invoice_data.total_tax:.2f} calculated correctly',
                severity=Severity.HIGH
            )
        else:
            return CheckResult(
                check_id='C3',
                check_name='Tax Calculation Accuracy',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Tax mismatch: Expected ₹{calculated_tax:.2f}, got ₹{invoice_data.total_tax:.2f}',
                severity=Severity.CRITICAL
            )
    
    async def _check_c10_total_amount(self, invoice_data: InvoiceData) -> CheckResult:
        """C10: Total amount = subtotal + tax"""
        
        calculated_total = invoice_data.subtotal + invoice_data.total_tax
        
        if abs(calculated_total - invoice_data.total_amount) <= 1.0:
            return CheckResult(
                check_id='C10',
                check_name='Total Amount Calculation',
                status=CheckStatus.PASS,
                confidence=1.0,
                reasoning=f'Total amount ₹{invoice_data.total_amount:.2f} calculated correctly',
                severity=Severity.CRITICAL
            )
        else:
            return CheckResult(
                check_id='C10',
                check_name='Total Amount Calculation',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Total mismatch: Expected ₹{calculated_total:.2f}, got ₹{invoice_data.total_amount:.2f}',
                severity=Severity.CRITICAL
            )
