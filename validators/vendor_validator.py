"""
Vendor Validation (Part of Category A - Document Authenticity)
Validates vendor information and status
"""

from models.invoice import InvoiceData
from models.validation import CheckResult, CategoryResult, CheckStatus, Severity
from utils.data_loaders import VendorRegistry


class VendorValidator:
    """
    Vendor Validation - Part of Category A
    Validates vendor information against registry
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        try:
            self.vendor_registry = VendorRegistry()
        except Exception as e:
            print(f"Warning: Could not load vendor registry: {e}")
            self.vendor_registry = None
    
    async def validate(self, invoice_data: InvoiceData, state=None) -> CategoryResult:
        """Execute vendor validation checks"""
        
        checks = []
        
        # A6: Seller details match vendor registry
        checks.append(await self._check_a6_seller_in_registry(invoice_data))
        
        # A7: Buyer GSTIN validation (if it's us)
        checks.append(await self._check_a7_buyer_gstin(invoice_data))
        
        # Additional: Check vendor status
        checks.append(await self._check_vendor_status(invoice_data))
        
        # Additional: Check for related party transactions
        checks.append(await self._check_related_party(invoice_data))
        
        return CategoryResult(
            category='A',
            category_name='Vendor Validation',
            checks=checks
        )
    
    async def _check_a6_seller_in_registry(self, invoice_data: InvoiceData) -> CheckResult:
        """A6: Seller details match vendor registry (Medium complexity)"""
        
        if not self.vendor_registry:
            return CheckResult(
                check_id='A6',
                check_name='Seller in Vendor Registry',
                status=CheckStatus.WARNING,
                confidence=0.0,
                reasoning='Vendor registry not available',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        
        try:
            vendor = self.vendor_registry.get_by_gstin(invoice_data.seller_gstin)
            
            # Vendor found - check name match
            registry_name = vendor['legal_name'].upper()
            invoice_name = invoice_data.seller_name.upper()
            
            # Simple name matching (in production, use fuzzy matching)
            if registry_name in invoice_name or invoice_name in registry_name:
                return CheckResult(
                    check_id='A6',
                    check_name='Seller in Vendor Registry',
                    status=CheckStatus.PASS,
                    confidence=0.95,
                    reasoning=f'Vendor found: {vendor["legal_name"]} (ID: {vendor["vendor_id"]})',
                    severity=Severity.MEDIUM
                )
            else:
                return CheckResult(
                    check_id='A6',
                    check_name='Seller in Vendor Registry',
                    status=CheckStatus.WARNING,
                    confidence=0.7,
                    reasoning=f'Vendor GSTIN found but name mismatch. Registry: {vendor["legal_name"]}, Invoice: {invoice_data.seller_name}',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
                
        except ValueError:
            # Vendor not found in registry
            return CheckResult(
                check_id='A6',
                check_name='Seller in Vendor Registry',
                status=CheckStatus.WARNING,
                confidence=0.8,
                reasoning=f'Vendor GSTIN {invoice_data.seller_gstin} not found in registry. May be new vendor.',
                severity=Severity.MEDIUM,
                requires_review=True
            )
    
    async def _check_a7_buyer_gstin(self, invoice_data: InvoiceData) -> CheckResult:
        """A7: Buyer GSTIN matches company records (Low complexity)"""
        
        # Company GSTIN from config (in production, load from company settings)
        company_gstin = "27AABCF9999K1ZX"  # FinanceGuard Solutions
        
        if invoice_data.buyer_gstin == company_gstin:
            return CheckResult(
                check_id='A7',
                check_name='Buyer GSTIN Validation',
                status=CheckStatus.PASS,
                confidence=1.0,
                reasoning=f'Buyer GSTIN matches company GSTIN: {company_gstin}',
                severity=Severity.HIGH
            )
        else:
            return CheckResult(
                check_id='A7',
                check_name='Buyer GSTIN Validation',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Buyer GSTIN mismatch. Expected: {company_gstin}, Found: {invoice_data.buyer_gstin}',
                severity=Severity.CRITICAL
            )
    
    async def _check_vendor_status(self, invoice_data: InvoiceData) -> CheckResult:
        """Check vendor status (active/suspended/cancelled)"""
        
        if not self.vendor_registry:
            return CheckResult(
                check_id='VENDOR_STATUS',
                check_name='Vendor Status Check',
                status=CheckStatus.WARNING,
                confidence=0.0,
                reasoning='Vendor registry not available',
                severity=Severity.HIGH,
                requires_review=True
            )
        
        try:
            vendor = self.vendor_registry.get_by_gstin(invoice_data.seller_gstin)
            
            status = vendor.get('status', 'UNKNOWN')
            
            if status == 'ACTIVE':
                return CheckResult(
                    check_id='VENDOR_STATUS',
                    check_name='Vendor Status Check',
                    status=CheckStatus.PASS,
                    confidence=0.95,
                    reasoning=f'Vendor status: ACTIVE',
                    severity=Severity.HIGH
                )
            elif status == 'SUSPENDED':
                return CheckResult(
                    check_id='VENDOR_STATUS',
                    check_name='Vendor Status Check',
                    status=CheckStatus.FAIL,
                    confidence=0.95,
                    reasoning=f'Vendor SUSPENDED since {vendor.get("suspension_date")}. Reason: {vendor.get("suspension_reason")}',
                    severity=Severity.CRITICAL,
                    requires_review=True
                )
            elif status == 'CANCELLED':
                return CheckResult(
                    check_id='VENDOR_STATUS',
                    check_name='Vendor Status Check',
                    status=CheckStatus.FAIL,
                    confidence=0.95,
                    reasoning=f'Vendor GSTIN CANCELLED',
                    severity=Severity.CRITICAL,
                    requires_review=True
                )
            else:
                return CheckResult(
                    check_id='VENDOR_STATUS',
                    check_name='Vendor Status Check',
                    status=CheckStatus.WARNING,
                    confidence=0.5,
                    reasoning=f'Vendor status unknown: {status}',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
                
        except ValueError:
            # Vendor not in registry - already flagged in A6
            return CheckResult(
                check_id='VENDOR_STATUS',
                check_name='Vendor Status Check',
                status=CheckStatus.WARNING,
                confidence=0.5,
                reasoning='Vendor not in registry - status cannot be verified',
                severity=Severity.MEDIUM,
                requires_review=True
            )
    
    async def _check_related_party(self, invoice_data: InvoiceData) -> CheckResult:
        """Check for related party transactions (same PAN, different GSTIN)"""
        
        if not self.vendor_registry:
            return CheckResult(
                check_id='RELATED_PARTY',
                check_name='Related Party Transaction Check',
                status=CheckStatus.WARNING,
                confidence=0.0,
                reasoning='Vendor registry not available',
                severity=Severity.MEDIUM
            )
        
        try:
            is_related = self.vendor_registry.is_related_party(invoice_data.seller_gstin)
            
            if is_related:
                vendor = self.vendor_registry.get_by_gstin(invoice_data.seller_gstin)
                return CheckResult(
                    check_id='RELATED_PARTY',
                    check_name='Related Party Transaction Check',
                    status=CheckStatus.WARNING,
                    confidence=0.9,
                    reasoning=f'Related party transaction detected. Vendor shares PAN {vendor.get("pan")} with other entities. Requires higher approval level.',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
            else:
                return CheckResult(
                    check_id='RELATED_PARTY',
                    check_name='Related Party Transaction Check',
                    status=CheckStatus.PASS,
                    confidence=0.9,
                    reasoning='Not a related party transaction',
                    severity=Severity.LOW
                )
                
        except ValueError:
            # Vendor not in registry
            return CheckResult(
                check_id='RELATED_PARTY',
                check_name='Related Party Transaction Check',
                status=CheckStatus.WARNING,
                confidence=0.5,
                reasoning='Cannot verify - vendor not in registry',
                severity=Severity.LOW
            )
    
    def get_vendor_info(self, gstin: str) -> dict:
        """Get vendor information for use by other validators"""
        
        if not self.vendor_registry:
            return {}
        
        try:
            return self.vendor_registry.get_by_gstin(gstin)
        except ValueError:
            return {}
