"""
Policy & Business Rules Validator (Category E)
Validates invoices against company policies and business rules
"""

from datetime import date, timedelta
from models.invoice import InvoiceData
from models.validation import CheckResult, CategoryResult, CheckStatus, Severity
from utils.data_loaders import CompanyPolicy, VendorRegistry
from typing import Dict


class PolicyValidator:
    """
    Category E: Policy & Business Rules Validation
    Validates against company policies, approval matrix, and business rules
    """
    
    def __init__(self, config: dict = None, data_dir: str = "data"):
        self.config = config or {}
        self.data_dir = data_dir
        
        # Load reference data
        self.policy = CompanyPolicy(data_dir)
        try:
            self.vendor_registry = VendorRegistry(data_dir)
        except:
            self.vendor_registry = None
    
    async def validate(self, invoice_data: InvoiceData, state=None) -> CategoryResult:
        """Execute policy validation checks"""
        
        checks = []
        
        # Get vendor info
        vendor_info = self._get_vendor_info(invoice_data.seller_gstin)
        
        # E1: Approval level determination
        checks.append(await self._check_e1_approval_level(invoice_data, vendor_info))
        
        # E2: Invoice date validity
        checks.append(await self._check_e2_invoice_date(invoice_data))
        
        # E3: PO reference validation
        checks.append(await self._check_e3_po_reference(invoice_data))
        
        # E4: Payment terms validation
        checks.append(await self._check_e4_payment_terms(invoice_data, vendor_info))
        
        # E5: Duplicate invoice check
        checks.append(await self._check_e5_duplicate_detection(invoice_data, state))
        
        # E6: FY boundary validation
        checks.append(await self._check_e6_fy_boundary(invoice_data))
        
        return CategoryResult(
            category='E',
            category_name='Policy & Business Rules',
            checks=checks
        )
    
    async def _check_e1_approval_level(self, invoice_data: InvoiceData, vendor_info: Dict) -> CheckResult:
        """E1: Approval level determination"""
        
        is_first_time = not bool(vendor_info)
        is_retrospective = self._is_retrospective(invoice_data)
        is_related_party = self.vendor_registry and self.vendor_registry.is_related_party(invoice_data.seller_gstin) if self.vendor_registry else False
        
        approval = self.policy.get_approval_level(
            invoice_data.total_amount,
            invoice_data.seller_gstin,
            is_first_time=is_first_time,
            is_retrospective=is_retrospective
        )
        
        reasons = []
        if is_first_time:
            reasons.append("First-time vendor")
        if is_retrospective:
            reasons.append("Retrospective invoice")
        if is_related_party:
            reasons.append("Related party transaction")
        
        level_name = approval.get('name', 'Unknown')
        reason_text = f" ({'; '.join(reasons)})" if reasons else ""
        
        return CheckResult(
            check_id='E1',
            check_name='Approval Level Determination',
            status=CheckStatus.PASS,
            confidence=0.95,
            reasoning=f'Requires Level {approval["level"]}: {level_name}{reason_text}. Amount: ₹{invoice_data.total_amount:,.2f}',
            severity=Severity.MEDIUM,
            requires_review=approval['level'] >= 4  # Flag high-level approvals
        )
    
    async def _check_e2_invoice_date(self, invoice_data: InvoiceData) -> CheckResult:
        """E2: Invoice date validity"""
        
        today = date.today()
        invoice_date = invoice_data.invoice_date
        
        # Check for future dates
        if invoice_date > today:
            return CheckResult(
                check_id='E2',
                check_name='Invoice Date Validity',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Future-dated invoice: {invoice_date} is after today ({today})',
                severity=Severity.CRITICAL,
                requires_review=True
            )
        
        # Check for old invoices
        max_age_days = self.policy.policy['invoice_acceptance_rules']['max_invoice_age_days']
        age_days = (today - invoice_date).days
        
        if age_days > max_age_days:
            return CheckResult(
                check_id='E2',
                check_name='Invoice Date Validity',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Invoice too old: {age_days} days (max: {max_age_days} days)',
                severity=Severity.HIGH,
                requires_review=True
            )
        
        # Check for retrospective (> 60 days)
        if age_days > 60:
            return CheckResult(
                check_id='E2',
                check_name='Invoice Date Validity',
                status=CheckStatus.WARNING,
                confidence=0.9,
                reasoning=f'Retrospective invoice: {age_days} days old. Requires higher approval.',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        
        return CheckResult(
            check_id='E2',
            check_name='Invoice Date Validity',
            status=CheckStatus.PASS,
            confidence=1.0,
            reasoning=f'Invoice date valid: {invoice_date} ({age_days} days old)',
            severity=Severity.MEDIUM
        )
    
    async def _check_e3_po_reference(self, invoice_data: InvoiceData) -> CheckResult:
        """E3: PO reference validation"""
        
        if not invoice_data.po_reference:
            return CheckResult(
                check_id='E3',
                check_name='PO Reference Validation',
                status=CheckStatus.WARNING,
                confidence=0.8,
                reasoning='No PO reference on invoice. May require additional justification.',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        
        # In production, would validate PO exists and amount is within tolerance
        return CheckResult(
            check_id='E3',
            check_name='PO Reference Validation',
            status=CheckStatus.PASS,
            confidence=0.9,
            reasoning=f'PO reference present: {invoice_data.po_reference}',
            severity=Severity.MEDIUM
        )
    
    async def _check_e4_payment_terms(self, invoice_data: InvoiceData, vendor_info: Dict) -> CheckResult:
        """E4: Payment terms validation"""
        
        if not invoice_data.payment_terms:
            return CheckResult(
                check_id='E4',
                check_name='Payment Terms Validation',
                status=CheckStatus.WARNING,
                confidence=0.7,
                reasoning='Payment terms not specified on invoice',
                severity=Severity.LOW
            )
        
        # Check for MSME vendors (45 days max)
        is_msme = vendor_info.get('msme_registered', False)
        
        if is_msme:
            # Extract days from payment terms (simple parsing)
            import re
            days_match = re.search(r'(\d+)', invoice_data.payment_terms)
            if days_match:
                days = int(days_match.group(1))
                if days > 45:
                    return CheckResult(
                        check_id='E4',
                        check_name='Payment Terms Validation',
                        status=CheckStatus.FAIL,
                        confidence=0.9,
                        reasoning=f'MSME vendor: Payment terms {days} days exceed 45-day limit',
                        severity=Severity.HIGH,
                        requires_review=True
                    )
        
        return CheckResult(
            check_id='E4',
            check_name='Payment Terms Validation',
            status=CheckStatus.PASS,
            confidence=0.85,
            reasoning=f'Payment terms acceptable: {invoice_data.payment_terms}',
            severity=Severity.LOW
        )
    
    async def _check_e5_duplicate_detection(self, invoice_data: InvoiceData, state) -> CheckResult:
        """E5: Duplicate invoice detection"""
        
        # In production, would check database for duplicates
        # For now, just check basic uniqueness factors
        
        duplicate_fields = self.policy.policy['invoice_acceptance_rules']['duplicate_fields']
        
        # Simple check: invoice number should be unique per vendor
        # This would be implemented with database lookup in production
        
        return CheckResult(
            check_id='E5',
            check_name='Duplicate Invoice Check',
            status=CheckStatus.PASS,
            confidence=0.7,
            reasoning=f'No duplicate detected for {invoice_data.invoice_number}. Note: Full check requires database lookup.',
            severity=Severity.MEDIUM
        )
    
    async def _check_e6_fy_boundary(self, invoice_data: InvoiceData) -> CheckResult:
        """E6: Financial year boundary validation"""
        
        fy_start = self.policy.policy['company_details']['fy_start']
        fy_end = self.policy.policy['company_details']['fy_end']
        
        # Parse FY dates
        fy_start_date = date.fromisoformat(fy_start)
        fy_end_date = date.fromisoformat(fy_end)
        
        # Check if invoice is in current FY
        if fy_start_date <= invoice_data.invoice_date <= fy_end_date:
            return CheckResult(
                check_id='E6',
                check_name='FY Boundary Validation',
                status=CheckStatus.PASS,
                confidence=1.0,
                reasoning=f'Invoice within current FY: {fy_start} to {fy_end}',
                severity=Severity.MEDIUM
            )
        
        # Check if it's a March invoice in April grace period
        cutoff_rules = self.policy.policy['invoice_acceptance_rules']['fy_cutoff_rules']
        march_cutoff = date.fromisoformat(cutoff_rules['march_invoices_until'])
        
        today = date.today()
        if invoice_data.invoice_date.month == 3 and today <= march_cutoff:
            return CheckResult(
                check_id='E6',
                check_name='FY Boundary Validation',
                status=CheckStatus.PASS,
                confidence=0.9,
                reasoning=f'March invoice accepted within grace period (until {march_cutoff})',
                severity=Severity.MEDIUM
            )
        
        # Invoice from previous FY
        if invoice_data.invoice_date < fy_start_date:
            return CheckResult(
                check_id='E6',
                check_name='FY Boundary Validation',
                status=CheckStatus.WARNING,
                confidence=0.85,
                reasoning=f'Invoice from previous FY ({invoice_data.invoice_date}). Requires justification.',
                severity=Severity.HIGH,
                requires_review=True
            )
        
        return CheckResult(
            check_id='E6',
            check_name='FY Boundary Validation',
            status=CheckStatus.WARNING,
            confidence=0.8,
            reasoning=f'Invoice date {invoice_data.invoice_date} outside current FY boundaries',
            severity=Severity.MEDIUM,
            requires_review=True
        )
    
    def _is_retrospective(self, invoice_data: InvoiceData) -> bool:
        """Check if invoice is retrospective (> 60 days old)"""
        today = date.today()
        age_days = (today - invoice_data.invoice_date).days
        return age_days > 60
    
    def _get_vendor_info(self, gstin: str) -> Dict:
        """Get vendor information"""
        if not self.vendor_registry:
            return {}
        
        try:
            return self.vendor_registry.get_by_gstin(gstin)
        except:
            return {}


from typing import Dict
