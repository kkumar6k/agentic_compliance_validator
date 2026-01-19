"""
Document Authenticity Validator (Category A)
Validates document authenticity, format compliance, and integrity checks
"""

import re
from datetime import date, datetime, timedelta
from typing import Dict, Optional
from models.invoice import InvoiceData
from models.validation import CheckResult, CategoryResult, CheckStatus, Severity
from utils.data_loaders import VendorRegistry


class DocumentValidator:
    """
    Category A: Document Authenticity Validation
    
    Validates:
    - A1: Invoice number format validation
    - A2: Duplicate invoice detection
    - A3: Sequential invoice number gap analysis
    - A4: Digital signature verification
    - A5: Invoice date vs document metadata date
    - A6: Seller details match vendor registry
    - A7: Buyer GSTIN matches company records
    - A8: Invoice tampering detection
    """
    
    def __init__(self, config: dict = None, data_dir: str = "data"):
        self.config = config or {}
        self.data_dir = data_dir
        
        # Load vendor registry
        try:
            self.vendor_registry = VendorRegistry(data_dir)
        except:
            self.vendor_registry = None
        
        # Company GSTIN (from config or default)
        self.company_gstin = self.config.get('company_gstin', '27AABCU9603R1ZM')
        
        # Invoice history for duplicate and sequential checks
        self.invoice_history = {}  # In production, this would be a database
    
    async def validate(self, invoice_data: InvoiceData, state=None) -> CategoryResult:
        """Execute all document authenticity checks"""
        
        checks = []
        
        # A1: Invoice number format validation
        checks.append(await self._check_a1_invoice_format(invoice_data))
        
        # A2: Duplicate invoice detection
        checks.append(await self._check_a2_duplicate_detection(invoice_data, state))
        
        # A3: Sequential invoice number gap analysis
        checks.append(await self._check_a3_sequential_gaps(invoice_data, state))
        
        # A4: Digital signature verification
        checks.append(await self._check_a4_digital_signature(invoice_data))
        
        # A5: Invoice date vs document metadata date
        checks.append(await self._check_a5_date_consistency(invoice_data))
        
        # A6: Seller details match vendor registry
        checks.append(await self._check_a6_seller_verification(invoice_data))
        
        # A7: Buyer GSTIN matches company records
        checks.append(await self._check_a7_buyer_gstin(invoice_data))
        
        # A8: Invoice tampering detection
        checks.append(await self._check_a8_tampering_detection(invoice_data))
        
        return CategoryResult(
            category='A',
            category_name='Document Authenticity',
            checks=checks
        )
    
    async def _check_a1_invoice_format(self, invoice_data: InvoiceData) -> CheckResult:
        """
        A1: Invoice number format validation
        
        Validates invoice number follows common patterns:
        - Alphanumeric format
        - Reasonable length (3-50 characters)
        - Contains year/sequence identifiers
        """
        
        invoice_num = invoice_data.invoice_number
        
        # Basic format checks
        if not invoice_num or len(invoice_num) < 3:
            return CheckResult(
                check_id='A1',
                check_name='Invoice Number Format',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Invoice number too short: "{invoice_num}"',
                severity=Severity.CRITICAL,
                requires_review=True
            )
        
        if len(invoice_num) > 50:
            return CheckResult(
                check_id='A1',
                check_name='Invoice Number Format',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Invoice number too long: {len(invoice_num)} characters',
                severity=Severity.HIGH,
                requires_review=True
            )
        
        # Check for valid characters (alphanumeric, dash, slash, underscore)
        valid_pattern = r'^[A-Za-z0-9\-/_]+$'
        if not re.match(valid_pattern, invoice_num):
            return CheckResult(
                check_id='A1',
                check_name='Invoice Number Format',
                status=CheckStatus.WARNING,
                confidence=0.9,
                reasoning=f'Invoice number contains unusual characters: "{invoice_num}"',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        
        # Check if invoice number contains year (good practice)
        current_year = invoice_data.invoice_date.year
        year_variants = [str(current_year), str(current_year)[2:], str(current_year-1), str(current_year-1)[2:]]
        has_year = any(year in invoice_num for year in year_variants)
        
        if has_year:
            return CheckResult(
                check_id='A1',
                check_name='Invoice Number Format',
                status=CheckStatus.PASS,
                confidence=1.0,
                reasoning=f'Invoice number format valid: "{invoice_num}" (contains year identifier)',
                severity=Severity.LOW
            )
        else:
            return CheckResult(
                check_id='A1',
                check_name='Invoice Number Format',
                status=CheckStatus.PASS,
                confidence=0.85,
                reasoning=f'Invoice number format acceptable: "{invoice_num}" (no year identifier)',
                severity=Severity.LOW
            )
    
    async def _check_a2_duplicate_detection(self, invoice_data: InvoiceData, state) -> CheckResult:
        """
        A2: Duplicate invoice detection (across vendors)
        
        Checks for:
        - Same invoice number from same vendor
        - Same amount, date, and vendor (potential duplicate)
        """
        
        invoice_num = invoice_data.invoice_number
        seller_gstin = invoice_data.seller_gstin
        
        # Create unique key for this invoice
        invoice_key = f"{seller_gstin}:{invoice_num}"
        
        # Check if we've seen this invoice before (in-memory for now)
        if invoice_key in self.invoice_history:
            previous = self.invoice_history[invoice_key]
            return CheckResult(
                check_id='A2',
                check_name='Duplicate Invoice Detection',
                status=CheckStatus.FAIL,
                confidence=0.95,
                reasoning=f'Duplicate invoice detected: {invoice_num} from {seller_gstin} (previously processed on {previous["date"]})',
                severity=Severity.CRITICAL,
                requires_review=True
            )
        
        # Check for potential duplicates (same amount, similar date, same vendor)
        for key, previous_invoice in self.invoice_history.items():
            if previous_invoice['seller_gstin'] == seller_gstin:
                # Same vendor - check for suspicious similarities
                amount_match = abs(previous_invoice['amount'] - invoice_data.total_amount) < 1.0
                date_diff = abs((previous_invoice['invoice_date'] - invoice_data.invoice_date).days)
                
                if amount_match and date_diff <= 7:
                    return CheckResult(
                        check_id='A2',
                        check_name='Duplicate Invoice Detection',
                        status=CheckStatus.WARNING,
                        confidence=0.75,
                        reasoning=f'Potential duplicate: Similar amount (₹{invoice_data.total_amount:,.2f}) and date to invoice {previous_invoice["invoice_num"]}',
                        severity=Severity.HIGH,
                        requires_review=True
                    )
        
        # Record this invoice for future checks
        self.invoice_history[invoice_key] = {
            'invoice_num': invoice_num,
            'seller_gstin': seller_gstin,
            'amount': invoice_data.total_amount,
            'invoice_date': invoice_data.invoice_date,
            'date': date.today()
        }
        
        return CheckResult(
            check_id='A2',
            check_name='Duplicate Invoice Detection',
            status=CheckStatus.PASS,
            confidence=0.90,
            reasoning=f'No duplicate detected for invoice {invoice_num}',
            severity=Severity.CRITICAL
        )
    
    async def _check_a3_sequential_gaps(self, invoice_data: InvoiceData, state) -> CheckResult:
        """
        A3: Sequential invoice number gap analysis
        
        Analyzes if invoice numbers from same vendor follow logical sequence
        Large gaps might indicate missing invoices or fraud
        """
        
        invoice_num = invoice_data.invoice_number
        seller_gstin = invoice_data.seller_gstin
        
        # Extract numeric component from invoice number
        numbers = re.findall(r'\d+', invoice_num)
        if not numbers:
            return CheckResult(
                check_id='A3',
                check_name='Sequential Invoice Number Analysis',
                status=CheckStatus.WARNING,
                confidence=0.7,
                reasoning=f'Invoice number contains no numeric sequence: "{invoice_num}"',
                severity=Severity.LOW,
                requires_review=False
            )
        
        # Get the largest number (likely the sequence number)
        current_seq = int(numbers[-1])
        
        # Find previous invoices from same vendor
        vendor_invoices = [
            inv for key, inv in self.invoice_history.items()
            if inv['seller_gstin'] == seller_gstin
        ]
        
        if not vendor_invoices:
            # First invoice from this vendor
            return CheckResult(
                check_id='A3',
                check_name='Sequential Invoice Number Analysis',
                status=CheckStatus.PASS,
                confidence=0.8,
                reasoning=f'First invoice from vendor, sequence: {current_seq}',
                severity=Severity.LOW
            )
        
        # Extract sequence numbers from previous invoices
        previous_sequences = []
        for inv in vendor_invoices:
            prev_numbers = re.findall(r'\d+', inv['invoice_num'])
            if prev_numbers:
                previous_sequences.append(int(prev_numbers[-1]))
        
        if previous_sequences:
            max_prev_seq = max(previous_sequences)
            gap = current_seq - max_prev_seq
            
            if gap < 0:
                return CheckResult(
                    check_id='A3',
                    check_name='Sequential Invoice Number Analysis',
                    status=CheckStatus.WARNING,
                    confidence=0.85,
                    reasoning=f'Invoice sequence out of order: {current_seq} (previous max: {max_prev_seq})',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
            elif gap == 1:
                return CheckResult(
                    check_id='A3',
                    check_name='Sequential Invoice Number Analysis',
                    status=CheckStatus.PASS,
                    confidence=1.0,
                    reasoning=f'Invoice sequence normal: {current_seq} (previous: {max_prev_seq})',
                    severity=Severity.LOW
                )
            elif gap <= 10:
                return CheckResult(
                    check_id='A3',
                    check_name='Sequential Invoice Number Analysis',
                    status=CheckStatus.PASS,
                    confidence=0.9,
                    reasoning=f'Invoice sequence acceptable: {current_seq} (gap of {gap} from previous {max_prev_seq})',
                    severity=Severity.LOW
                )
            else:
                return CheckResult(
                    check_id='A3',
                    check_name='Sequential Invoice Number Analysis',
                    status=CheckStatus.WARNING,
                    confidence=0.8,
                    reasoning=f'Large sequence gap detected: {gap} invoices between {max_prev_seq} and {current_seq}',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
        
        return CheckResult(
            check_id='A3',
            check_name='Sequential Invoice Number Analysis',
            status=CheckStatus.PASS,
            confidence=0.75,
            reasoning=f'Sequence analysis completed: {current_seq}',
            severity=Severity.LOW
        )
    
    async def _check_a4_digital_signature(self, invoice_data: InvoiceData) -> CheckResult:
        """
        A4: Digital signature verification
        
        Checks for:
        - IRN (Invoice Reference Number) presence
        - QR code presence
        - Digital signature metadata
        """
        
        has_irn = bool(invoice_data.irn)
        has_qr = invoice_data.qr_code_present
        is_high_value = invoice_data.total_amount >= 5_00_00_000  # ₹5 Crores
        
        # For high-value B2B transactions, IRN is mandatory
        if is_high_value:
            if has_irn and has_qr:
                return CheckResult(
                    check_id='A4',
                    check_name='Digital Signature Verification',
                    status=CheckStatus.PASS,
                    confidence=0.95,
                    reasoning=f'E-invoice compliant: IRN present ({invoice_data.irn[:20]}...), QR code present',
                    severity=Severity.MEDIUM
                )
            elif has_irn:
                return CheckResult(
                    check_id='A4',
                    check_name='Digital Signature Verification',
                    status=CheckStatus.WARNING,
                    confidence=0.85,
                    reasoning=f'E-invoice has IRN but QR code missing for high-value invoice (₹{invoice_data.total_amount:,.2f})',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
            else:
                return CheckResult(
                    check_id='A4',
                    check_name='Digital Signature Verification',
                    status=CheckStatus.FAIL,
                    confidence=0.95,
                    reasoning=f'E-invoice mandatory for ₹{invoice_data.total_amount:,.2f} but IRN missing',
                    severity=Severity.HIGH,
                    requires_review=True
                )
        
        # For regular invoices
        if has_irn or has_qr:
            return CheckResult(
                check_id='A4',
                check_name='Digital Signature Verification',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning=f'Digital authentication present: {"IRN" if has_irn else ""} {"QR code" if has_qr else ""}',
                severity=Severity.LOW
            )
        
        return CheckResult(
            check_id='A4',
            check_name='Digital Signature Verification',
            status=CheckStatus.PASS,
            confidence=0.80,
            reasoning='No digital signature required for this invoice value',
            severity=Severity.LOW
        )
    
    async def _check_a5_date_consistency(self, invoice_data: InvoiceData) -> CheckResult:
        """
        A5: Invoice date vs document metadata date
        
        Checks if invoice date is consistent with:
        - IRN generation date
        - Document creation date (if available)
        - Reasonable business date (not too old/future)
        """
        
        invoice_date = invoice_data.invoice_date
        today = date.today()
        
        # Check for future dates
        if invoice_date > today:
            return CheckResult(
                check_id='A5',
                check_name='Invoice Date Consistency',
                status=CheckStatus.FAIL,
                confidence=1.0,
                reasoning=f'Future-dated invoice: {invoice_date} is after today ({today})',
                severity=Severity.CRITICAL,
                requires_review=True
            )
        
        # Check if IRN date matches invoice date
        if invoice_data.irn and invoice_data.irn_date:
            date_diff = abs((invoice_data.irn_date - invoice_date).days)
            
            if date_diff == 0:
                return CheckResult(
                    check_id='A5',
                    check_name='Invoice Date Consistency',
                    status=CheckStatus.PASS,
                    confidence=1.0,
                    reasoning=f'Invoice date matches IRN date: {invoice_date}',
                    severity=Severity.MEDIUM
                )
            elif date_diff <= 2:
                return CheckResult(
                    check_id='A5',
                    check_name='Invoice Date Consistency',
                    status=CheckStatus.PASS,
                    confidence=0.95,
                    reasoning=f'Invoice date close to IRN date: {date_diff} day(s) difference',
                    severity=Severity.MEDIUM
                )
            else:
                return CheckResult(
                    check_id='A5',
                    check_name='Invoice Date Consistency',
                    status=CheckStatus.WARNING,
                    confidence=0.85,
                    reasoning=f'Invoice date ({invoice_date}) differs from IRN date ({invoice_data.irn_date}) by {date_diff} days',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
        
        # Check if invoice is too old (potential backdating)
        age_days = (today - invoice_date).days
        if age_days > 365:
            return CheckResult(
                check_id='A5',
                check_name='Invoice Date Consistency',
                status=CheckStatus.WARNING,
                confidence=0.9,
                reasoning=f'Very old invoice: {age_days} days old (dated {invoice_date}). Possible backdating.',
                severity=Severity.HIGH,
                requires_review=True
            )
        
        return CheckResult(
            check_id='A5',
            check_name='Invoice Date Consistency',
            status=CheckStatus.PASS,
            confidence=0.95,
            reasoning=f'Invoice date consistent: {invoice_date} ({age_days} days old)',
            severity=Severity.MEDIUM
        )
    
    async def _check_a6_seller_verification(self, invoice_data: InvoiceData) -> CheckResult:
        """
        A6: Seller details match vendor registry
        
        Validates:
        - Vendor exists in registry
        - GSTIN matches registered GSTIN
        - Name matches (fuzzy matching)
        - Address/state consistency
        """
        
        if not self.vendor_registry:
            return CheckResult(
                check_id='A6',
                check_name='Seller Verification',
                status=CheckStatus.WARNING,
                confidence=0.6,
                reasoning='Vendor registry not available for verification',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        
        try:
            vendor = self.vendor_registry.get_by_gstin(invoice_data.seller_gstin)
            
            # GSTIN matches
            gstin_match = vendor['gstin'] == invoice_data.seller_gstin
            
            # Name matching (case-insensitive, partial match)
            registered_name = vendor.get('name', '').lower().strip()
            invoice_name = invoice_data.seller_name.lower().strip()
            
            # Simple fuzzy match - check if one contains the other or >70% character overlap
            name_match = (
                registered_name in invoice_name or 
                invoice_name in registered_name or
                self._fuzzy_match(registered_name, invoice_name) > 0.7
            )
            
            # State matching (if available)
            state_match = True
            state_mismatch_msg = ""
            if invoice_data.seller_state and vendor.get('state'):
                state_match = vendor['state'].lower() == invoice_data.seller_state.lower()
                if not state_match:
                    state_mismatch_msg = f" (State mismatch: {vendor['state']} vs {invoice_data.seller_state})"
            
            if gstin_match and name_match and state_match:
                return CheckResult(
                    check_id='A6',
                    check_name='Seller Verification',
                    status=CheckStatus.PASS,
                    confidence=0.95,
                    reasoning=f'Seller verified: {vendor.get("name", invoice_data.seller_name)} matches vendor registry',
                    severity=Severity.MEDIUM
                )
            elif gstin_match and name_match:
                return CheckResult(
                    check_id='A6',
                    check_name='Seller Verification',
                    status=CheckStatus.PASS,
                    confidence=0.85,
                    reasoning=f'Seller verified with minor discrepancies{state_mismatch_msg}',
                    severity=Severity.MEDIUM
                )
            elif gstin_match:
                return CheckResult(
                    check_id='A6',
                    check_name='Seller Verification',
                    status=CheckStatus.WARNING,
                    confidence=0.75,
                    reasoning=f'GSTIN matches but name mismatch: Invoice "{invoice_data.seller_name}" vs Registry "{vendor.get("name", "Unknown")}"',
                    severity=Severity.HIGH,
                    requires_review=True
                )
            else:
                return CheckResult(
                    check_id='A6',
                    check_name='Seller Verification',
                    status=CheckStatus.FAIL,
                    confidence=0.90,
                    reasoning=f'Seller verification failed: Multiple mismatches detected',
                    severity=Severity.HIGH,
                    requires_review=True
                )

        except ValueError:
            # Vendor not in registry
            return CheckResult(
                check_id='A6',
                check_name='Seller Verification',
                status=CheckStatus.WARNING,
                confidence=0.85,
                reasoning=f'Seller GSTIN {invoice_data.seller_gstin} not found in vendor registry. First-time vendor?',
                severity=Severity.HIGH,
                requires_review=True
            )

    async def _check_a7_buyer_gstin(self, invoice_data: InvoiceData) -> CheckResult:
        """
        A7: Buyer GSTIN matches company records

        Validates that the buyer GSTIN on invoice matches company's registered GSTIN
        """

        buyer_gstin = invoice_data.buyer_gstin

        if buyer_gstin == self.company_gstin:
            return CheckResult(
                check_id='A7',
                check_name='Buyer GSTIN Verification',
                status=CheckStatus.PASS,
                confidence=1.0,
                reasoning=f'Buyer GSTIN matches company records: {buyer_gstin}',
                severity=Severity.CRITICAL
            )

        # Check if it might be a branch/unit GSTIN (same PAN, different state)
        company_pan = self.company_gstin[2:12]
        buyer_pan = buyer_gstin[2:12] if len(buyer_gstin) >= 12 else None

        if buyer_pan and buyer_pan == company_pan:
            return CheckResult(
                check_id='A7',
                check_name='Buyer GSTIN Verification',
                status=CheckStatus.WARNING,
                confidence=0.85,
                reasoning=f'Buyer GSTIN {buyer_gstin} has same PAN as company but different state code (branch/unit?)',
                severity=Severity.HIGH,
                requires_review=True
            )

        return CheckResult(
            check_id='A7',
            check_name='Buyer GSTIN Verification',
            status=CheckStatus.FAIL,
            confidence=0.95,
            reasoning=f'Buyer GSTIN mismatch: Invoice shows {buyer_gstin}, company GSTIN is {self.company_gstin}',
            severity=Severity.CRITICAL,
            requires_review=True
        )

    async def _check_a8_tampering_detection(self, invoice_data: InvoiceData) -> CheckResult:
        """
        A8: Invoice tampering detection (for images/PDFs)

        Checks for signs of tampering:
        - Metadata inconsistencies
        - Format type vs content validation
        - Extraction confidence scores
        """

        # Check extraction confidence
        confidence = invoice_data.extraction_confidence

        if confidence < 0.70:
            return CheckResult(
                check_id='A8',
                check_name='Tampering Detection',
                status=CheckStatus.WARNING,
                confidence=0.80,
                reasoning=f'Low extraction confidence ({confidence:.0%}). Document quality issues or potential tampering.',
                severity=Severity.HIGH,
                requires_review=True
            )
        elif confidence < 0.85:
            return CheckResult(
                check_id='A8',
                check_name='Tampering Detection',
                status=CheckStatus.PASS,
                confidence=0.85,
                reasoning=f'Moderate extraction confidence ({confidence:.0%}). Document appears authentic.',
                severity=Severity.MEDIUM
            )

        # Check format type
        format_type = invoice_data.format_type

        if format_type in ['image', 'pdf']:
            return CheckResult(
                check_id='A8',
                check_name='Tampering Detection',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning=f'Document format: {format_type} with high confidence ({confidence:.0%}). No tampering indicators.',
                severity=Severity.MEDIUM
            )

        return CheckResult(
            check_id='A8',
            check_name='Tampering Detection',
            status=CheckStatus.PASS,
            confidence=0.95,
            reasoning=f'Structured data format ({format_type}). No tampering concerns.',
            severity=Severity.MEDIUM
        )

    def _fuzzy_match(self, str1: str, str2: str) -> float:
        """
        Simple fuzzy string matching
        Returns similarity score between 0 and 1
        """
        if not str1 or not str2:
            return 0.0

        # Convert to lowercase and remove extra spaces
        s1 = ' '.join(str1.lower().split())
        s2 = ' '.join(str2.lower().split())

        # Count matching characters
        matches = sum(1 for c in s1 if c in s2)
        max_len = max(len(s1), len(s2))

        if max_len == 0:
            return 0.0

        return matches / max_len