"""
TDS Compliance Validator (Category D)
Complete 12-point TDS validation for Indian tax deduction at source
"""

import re
from typing import Dict, List, Optional
from datetime import date, datetime
from models.invoice import InvoiceData
from models.validation import CheckResult, CategoryResult, CheckStatus, Severity
from utils.data_loaders import TDSSectionRules, VendorRegistry


class TDSValidator:
    """
    Category D: TDS Compliance Validation (12 checks)
    
    Validates:
    - D1-D3: TDS applicability and section determination
    - D4-D6: Rate validation and thresholds
    - D7-D9: Special cases (GST component, non-resident, TAN)
    - D10-D12: Higher rates and reconciliation
    """
    
    def __init__(self, config: dict = None, data_dir: str = "data"):
        self.config = config or {}
        self.data_dir = data_dir
        
        # Load TDS rules
        self.tds_sections = TDSSectionRules(data_dir)
        
        # Load vendor registry
        try:
            self.vendor_registry = VendorRegistry(data_dir)
        except:
            self.vendor_registry = None
        
        # TDS thresholds (FY 2024-25)
        self.thresholds = {
            '194C': 30000,     # Contractors (single)
            '194C_aggregate': 100000,  # Contractors (aggregate)
            '194J': 30000,     # Professional/technical services
            '194H': 15000,     # Commission/brokerage
            '194I': 180000,    # Rent - plant/machinery (single)
            '194I_property': 240000,  # Rent - land/building
            '194Q': 5000000,   # Purchase of goods
        }
        
        # Aggregate tracking (in production, this would be a database)
        self.aggregate_payments = {}
    
    async def validate(self, invoice_data: InvoiceData, state=None) -> CategoryResult:
        """Execute all TDS compliance checks"""
        
        checks = []
        
        # D1-D3: Basic TDS Applicability
        checks.append(await self._check_d1_tds_applicability(invoice_data))
        checks.append(await self._check_d2_section_determination(invoice_data))
        checks.append(await self._check_d3_rate_based_on_pan(invoice_data))
        
        # D4-D6: Thresholds and Limits
        checks.append(await self._check_d4_lower_deduction_certificate(invoice_data))
        checks.append(await self._check_d5_threshold_limit(invoice_data))
        checks.append(await self._check_d6_aggregate_threshold(invoice_data, state))
        
        # D7-D9: Special Cases
        checks.append(await self._check_d7_tds_on_gst(invoice_data))
        checks.append(await self._check_d8_non_resident_tds(invoice_data))
        checks.append(await self._check_d9_tan_validation(invoice_data))
        
        # D10-D12: Higher Rates and Reconciliation
        checks.append(await self._check_d10_section_206ab_higher_rate(invoice_data))
        checks.append(await self._check_d11_tds_certificate(invoice_data))
        checks.append(await self._check_d12_quarterly_reconciliation(invoice_data))
        
        return CategoryResult(
            category='D',
            category_name='TDS Compliance',
            checks=checks
        )
    
    async def _check_d1_tds_applicability(self, invoice_data: InvoiceData) -> CheckResult:
        """D1: TDS applicability based on vendor type"""
        
        tds_marked = invoice_data.tds_applicable
        invoice_amount = invoice_data.total_amount
        
        # Get vendor information
        vendor_info = None
        if self.vendor_registry:
            try:
                vendor_info = self.vendor_registry.get_by_gstin(invoice_data.seller_gstin)
            except:
                pass
        
        # Determine if TDS should apply
        should_apply_tds = False
        reasons = []
        
        # Check 1: Amount threshold - TDS typically applies for amounts > ₹30,000
        if invoice_amount > 30000:
            should_apply_tds = True
            reasons.append(f"Amount ₹{invoice_amount:,.2f} exceeds basic threshold")
        
        # Check 2: Vendor type
        if vendor_info:
            vendor_type = vendor_info.get('vendor_type', 'OTHERS')
            
            if vendor_type in ['CONTRACTOR', 'PROFESSIONAL', 'CONSULTANT']:
                should_apply_tds = True
                reasons.append(f"Vendor type: {vendor_type}")
            
            # Check if vendor has PAN
            has_pan = bool(vendor_info.get('pan'))
            if not has_pan:
                should_apply_tds = True
                reasons.append("No PAN - higher TDS rate applies")
        
        # Check 3: Service keywords in line items
        service_keywords = ['service', 'professional', 'consulting', 'contract', 
                           'commission', 'rent', 'technical', 'legal', 'audit']
        
        for item in invoice_data.line_items:
            desc_lower = item.description.lower()
            if any(keyword in desc_lower for keyword in service_keywords):
                should_apply_tds = True
                reasons.append(f"Service detected: {item.description[:30]}")
                break
        
        # Compare with invoice marking
        if should_apply_tds and tds_marked:
            return CheckResult(
                check_id='D1',
                check_name='TDS Applicability',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning=f'TDS correctly marked. Reasons: {"; ".join(reasons[:2])}',
                severity=Severity.HIGH
            )
        elif should_apply_tds and not tds_marked:
            return CheckResult(
                check_id='D1',
                check_name='TDS Applicability',
                status=CheckStatus.FAIL,
                confidence=0.85,
                reasoning=f'TDS should apply but not marked. Reasons: {"; ".join(reasons[:2])}',
                severity=Severity.CRITICAL,
                requires_review=True
            )
        elif not should_apply_tds and tds_marked:
            return CheckResult(
                check_id='D1',
                check_name='TDS Applicability',
                status=CheckStatus.WARNING,
                confidence=0.75,
                reasoning='TDS marked but may not be applicable. Verify service type.',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        else:
            return CheckResult(
                check_id='D1',
                check_name='TDS Applicability',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable for this transaction type/amount',
                severity=Severity.MEDIUM
            )
    
    async def _check_d2_section_determination(self, invoice_data: InvoiceData) -> CheckResult:
        """D2: Section determination (194C/194J/194H etc.)"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D2',
                check_name='TDS Section Determination',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable - section determination not required',
                severity=Severity.LOW
            )
        
        invoice_section = invoice_data.tds_section
        invoice_amount = invoice_data.total_amount
        
        # Determine expected section based on description
        line_items = invoice_data.line_items
        expected_sections = []
        
        for item in line_items:
            desc_lower = item.description.lower()
            
            # 194C: Contractor payments
            if any(kw in desc_lower for kw in ['contract', 'works', 'construction', 'fabrication', 'labour']):
                expected_sections.append('194C')
            
            # 194J: Professional/technical services
            elif any(kw in desc_lower for kw in ['professional', 'technical', 'consulting', 'legal', 
                                                   'audit', 'accounting', 'design', 'engineering']):
                expected_sections.append('194J')
            
            # 194H: Commission/brokerage
            elif any(kw in desc_lower for kw in ['commission', 'brokerage', 'agent', 'referral']):
                expected_sections.append('194H')
            
            # 194I: Rent
            elif any(kw in desc_lower for kw in ['rent', 'lease', 'hire']):
                expected_sections.append('194I')
            
            # 194Q: Purchase of goods (> ₹50 lakhs)
            elif invoice_amount >= 5000000:
                expected_sections.append('194Q')
        
        if not expected_sections:
            expected_sections = ['194C']  # Default to contractor
        
        expected_section = expected_sections[0]
        
        if invoice_section:
            if invoice_section == expected_section:
                section_info = self.tds_sections.get_section(invoice_section)
                return CheckResult(
                    check_id='D2',
                    check_name='TDS Section Determination',
                    status=CheckStatus.PASS,
                    confidence=0.90,
                    reasoning=f'Correct section {invoice_section}: {section_info.get("description", "N/A") if section_info else ""}',
                    severity=Severity.HIGH
                )
            elif invoice_section in expected_sections:
                return CheckResult(
                    check_id='D2',
                    check_name='TDS Section Determination',
                    status=CheckStatus.PASS,
                    confidence=0.85,
                    reasoning=f'Section {invoice_section} is acceptable (also considered: {expected_section})',
                    severity=Severity.HIGH
                )
            else:
                return CheckResult(
                    check_id='D2',
                    check_name='TDS Section Determination',
                    status=CheckStatus.WARNING,
                    confidence=0.75,
                    reasoning=f'Section mismatch: Invoice shows {invoice_section}, expected {expected_section}',
                    severity=Severity.HIGH,
                    requires_review=True
                )
        else:
            return CheckResult(
                check_id='D2',
                check_name='TDS Section Determination',
                status=CheckStatus.FAIL,
                confidence=0.85,
                reasoning=f'TDS section not specified. Should be {expected_section}',
                severity=Severity.HIGH,
                requires_review=True
            )
    
    async def _check_d3_rate_based_on_pan(self, invoice_data: InvoiceData) -> CheckResult:
        """D3: TDS rate based on PAN availability"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D3',
                check_name='TDS Rate (PAN-based)',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable - rate validation not required',
                severity=Severity.LOW
            )
        
        tds_section = invoice_data.tds_section or '194C'
        invoice_rate = invoice_data.tds_rate or 0
        invoice_amount = invoice_data.tds_amount or 0
        
        # Get vendor PAN status
        has_pan = False
        if self.vendor_registry:
            try:
                vendor = self.vendor_registry.get_by_gstin(invoice_data.seller_gstin)
                has_pan = bool(vendor.get('pan'))
            except:
                # Extract PAN from GSTIN (characters 3-12)
                gstin = invoice_data.seller_gstin
                if len(gstin) >= 12:
                    pan_from_gstin = gstin[2:12]
                    has_pan = bool(pan_from_gstin and pan_from_gstin != '0000000000')
        
        # Get expected rate
        expected_rate = self.tds_sections.get_rate(tds_section, 'COMPANY', has_pan)
        
        if not has_pan:
            expected_rate = 20.0  # No PAN rate
        
        rate_diff = abs(invoice_rate - expected_rate)
        
        if rate_diff <= 0.1:  # Allow 0.1% tolerance
            return CheckResult(
                check_id='D3',
                check_name='TDS Rate (PAN-based)',
                status=CheckStatus.PASS,
                confidence=0.95,
                reasoning=f'Correct TDS rate: {invoice_rate}% ({"With" if has_pan else "Without"} PAN)',
                severity=Severity.HIGH
            )
        else:
            return CheckResult(
                check_id='D3',
                check_name='TDS Rate (PAN-based)',
                status=CheckStatus.FAIL,
                confidence=0.90,
                reasoning=f'TDS rate mismatch: Invoice {invoice_rate}% vs Expected {expected_rate}% ({"With" if has_pan else "Without"} PAN)',
                severity=Severity.HIGH,
                requires_review=True
            )
    
    async def _check_d4_lower_deduction_certificate(self, invoice_data: InvoiceData) -> CheckResult:
        """D4: Lower deduction certificate validation"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D4',
                check_name='Lower Deduction Certificate',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable - certificate not required',
                severity=Severity.LOW
            )
        
        tds_rate = invoice_data.tds_rate or 0
        tds_section = invoice_data.tds_section or '194C'
        
        # Get standard rate
        standard_rate = self.tds_sections.get_rate(tds_section, 'COMPANY', True)
        
        # Check if rate is lower than standard
        if tds_rate < standard_rate - 0.1:
            # Lower rate detected - should have certificate
            return CheckResult(
                check_id='D4',
                check_name='Lower Deduction Certificate',
                status=CheckStatus.WARNING,
                confidence=0.80,
                reasoning=f'Lower TDS rate ({tds_rate}% vs standard {standard_rate}%). Verify Form 13 certificate.',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        
        return CheckResult(
            check_id='D4',
            check_name='Lower Deduction Certificate',
            status=CheckStatus.PASS,
            confidence=0.90,
            reasoning=f'Standard TDS rate applied ({tds_rate}%) - certificate not required',
            severity=Severity.LOW
        )
    
    async def _check_d5_threshold_limit(self, invoice_data: InvoiceData) -> CheckResult:
        """D5: Threshold limit for TDS applicability"""
        
        invoice_amount = invoice_data.total_amount
        tds_section = invoice_data.tds_section or '194C'
        tds_marked = invoice_data.tds_applicable
        
        # Get threshold for section
        threshold = self.thresholds.get(tds_section, 30000)
        
        if invoice_amount < threshold:
            if tds_marked:
                return CheckResult(
                    check_id='D5',
                    check_name='TDS Threshold Limit',
                    status=CheckStatus.WARNING,
                    confidence=0.85,
                    reasoning=f'Invoice ₹{invoice_amount:,.2f} below {tds_section} threshold (₹{threshold:,}). TDS may not be required.',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
            else:
                return CheckResult(
                    check_id='D5',
                    check_name='TDS Threshold Limit',
                    status=CheckStatus.PASS,
                    confidence=0.95,
                    reasoning=f'Below threshold: ₹{invoice_amount:,.2f} < ₹{threshold:,}',
                    severity=Severity.MEDIUM
                )
        else:
            if tds_marked:
                return CheckResult(
                    check_id='D5',
                    check_name='TDS Threshold Limit',
                    status=CheckStatus.PASS,
                    confidence=0.95,
                    reasoning=f'Above threshold: ₹{invoice_amount:,.2f} > ₹{threshold:,} - TDS applicable',
                    severity=Severity.HIGH
                )
            else:
                return CheckResult(
                    check_id='D5',
                    check_name='TDS Threshold Limit',
                    status=CheckStatus.FAIL,
                    confidence=0.90,
                    reasoning=f'Above threshold: ₹{invoice_amount:,.2f} > ₹{threshold:,} - TDS should apply',
                    severity=Severity.HIGH,
                    requires_review=True
                )
    
    async def _check_d6_aggregate_threshold(self, invoice_data: InvoiceData, state) -> CheckResult:
        """D6: Aggregate payment threshold tracking"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D6',
                check_name='Aggregate Threshold Tracking',
                status=CheckStatus.PASS,
                confidence=0.80,
                reasoning='TDS not applicable - aggregate tracking not required',
                severity=Severity.LOW
            )
        
        vendor_gstin = invoice_data.seller_gstin
        invoice_amount = invoice_data.total_amount
        tds_section = invoice_data.tds_section or '194C'
        
        # Track aggregate payments (in production, query database)
        if vendor_gstin not in self.aggregate_payments:
            self.aggregate_payments[vendor_gstin] = {'total': 0, 'invoices': []}
        
        self.aggregate_payments[vendor_gstin]['total'] += invoice_amount
        self.aggregate_payments[vendor_gstin]['invoices'].append(invoice_data.invoice_number)
        
        aggregate_total = self.aggregate_payments[vendor_gstin]['total']
        
        # Check against aggregate threshold
        aggregate_threshold = self.thresholds.get(f'{tds_section}_aggregate', 100000)
        
        if aggregate_total >= aggregate_threshold:
            return CheckResult(
                check_id='D6',
                check_name='Aggregate Threshold Tracking',
                status=CheckStatus.WARNING,
                confidence=0.85,
                reasoning=f'Aggregate payments to vendor: ₹{aggregate_total:,.2f} (threshold: ₹{aggregate_threshold:,}). Ensure TDS applied on all payments.',
                severity=Severity.HIGH,
                requires_review=True
            )
        else:
            return CheckResult(
                check_id='D6',
                check_name='Aggregate Threshold Tracking',
                status=CheckStatus.PASS,
                confidence=0.85,
                reasoning=f'Aggregate tracking: ₹{aggregate_total:,.2f} / ₹{aggregate_threshold:,}',
                severity=Severity.MEDIUM
            )
    
    async def _check_d7_tds_on_gst(self, invoice_data: InvoiceData) -> CheckResult:
        """D7: TDS on GST component handling"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D7',
                check_name='TDS on GST Component',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable - GST treatment not relevant',
                severity=Severity.LOW
            )
        
        # TDS should be calculated on amount EXCLUDING GST (generally)
        # Exception: Certain sections like 194C may include GST
        
        tds_section = invoice_data.tds_section or '194C'
        subtotal = invoice_data.subtotal
        total_tax = (invoice_data.cgst_amount or 0) + (invoice_data.sgst_amount or 0) + (invoice_data.igst_amount or 0)
        total_amount = invoice_data.total_amount
        tds_amount = invoice_data.tds_amount or 0
        tds_rate = invoice_data.tds_rate or 0
        
        if tds_amount == 0:
            return CheckResult(
                check_id='D7',
                check_name='TDS on GST Component',
                status=CheckStatus.PASS,
                confidence=0.75,
                reasoning='No TDS deducted - GST treatment validation not applicable',
                severity=Severity.LOW
            )
        
        # Calculate expected TDS on subtotal (excluding GST)
        expected_tds_excl_gst = subtotal * tds_rate / 100
        
        # Calculate expected TDS on total (including GST) - for 194C
        expected_tds_incl_gst = total_amount * tds_rate / 100
        
        # Check which matches
        diff_excl = abs(tds_amount - expected_tds_excl_gst)
        diff_incl = abs(tds_amount - expected_tds_incl_gst)
        
        if diff_excl <= 1.0:
            return CheckResult(
                check_id='D7',
                check_name='TDS on GST Component',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning=f'TDS correctly calculated on amount excluding GST: ₹{tds_amount:,.2f}',
                severity=Severity.MEDIUM
            )
        elif diff_incl <= 1.0:
            if tds_section == '194C':
                return CheckResult(
                    check_id='D7',
                    check_name='TDS on GST Component',
                    status=CheckStatus.PASS,
                    confidence=0.85,
                    reasoning=f'TDS calculated on amount including GST: ₹{tds_amount:,.2f} (acceptable for 194C)',
                    severity=Severity.MEDIUM
                )
            else:
                return CheckResult(
                    check_id='D7',
                    check_name='TDS on GST Component',
                    status=CheckStatus.WARNING,
                    confidence=0.80,
                    reasoning=f'TDS includes GST component. Verify if correct for {tds_section}.',
                    severity=Severity.MEDIUM,
                    requires_review=True
                )
        else:
            return CheckResult(
                check_id='D7',
                check_name='TDS on GST Component',
                status=CheckStatus.WARNING,
                confidence=0.75,
                reasoning=f'TDS calculation unclear: ₹{tds_amount:,.2f} (Expected: ₹{expected_tds_excl_gst:,.2f} excl. or ₹{expected_tds_incl_gst:,.2f} incl. GST)',
                severity=Severity.MEDIUM,
                requires_review=True
            )
    
    async def _check_d8_non_resident_tds(self, invoice_data: InvoiceData) -> CheckResult:
        """D8: Non-resident TDS rules"""
        
        # Check if vendor is non-resident (indicated by GSTIN or vendor registry)
        vendor_gstin = invoice_data.seller_gstin
        
        # Non-resident suppliers typically have special GSTIN formats
        # or are marked in vendor registry
        
        is_non_resident = False
        if self.vendor_registry:
            try:
                vendor = self.vendor_registry.get_by_gstin(vendor_gstin)
                is_non_resident = vendor.get('resident_status', 'RESIDENT') == 'NON_RESIDENT'
            except:
                pass
        
        if not is_non_resident:
            return CheckResult(
                check_id='D8',
                check_name='Non-Resident TDS Rules',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='Resident Indian vendor - non-resident rules not applicable',
                severity=Severity.LOW
            )
        
        # For non-residents, different sections apply (195, 194LC, etc.)
        tds_section = invoice_data.tds_section
        tds_applicable = invoice_data.tds_applicable
        
        # Non-residents should have higher TDS rates or specific sections
        non_resident_sections = ['195', '194LC', '194LD']
        
        if not tds_applicable:
            return CheckResult(
                check_id='D8',
                check_name='Non-Resident TDS Rules',
                status=CheckStatus.FAIL,
                confidence=0.90,
                reasoning='Non-resident vendor but TDS not marked. Section 195 may apply.',
                severity=Severity.CRITICAL,
                requires_review=True
            )
        
        if tds_section in non_resident_sections:
            return CheckResult(
                check_id='D8',
                check_name='Non-Resident TDS Rules',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning=f'Non-resident TDS section {tds_section} correctly applied',
                severity=Severity.HIGH
            )
        else:
            return CheckResult(
                check_id='D8',
                check_name='Non-Resident TDS Rules',
                status=CheckStatus.WARNING,
                confidence=0.80,
                reasoning=f'Non-resident vendor with section {tds_section}. Verify if Section 195 applies.',
                severity=Severity.HIGH,
                requires_review=True
            )
    
    async def _check_d9_tan_validation(self, invoice_data: InvoiceData) -> CheckResult:
        """D9: TAN validation"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D9',
                check_name='TAN Validation',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable - TAN not required',
                severity=Severity.LOW
            )
        
        # TAN format: 4 letters + 5 digits + 1 letter (e.g., MUMM12345A)
        # In production, this would be the deductor's TAN
        # For this check, we validate format if TAN is present
        
        # TAN should be on the buyer's side (deductor), not in invoice data
        # But we can check if mentioned in notes/additional fields
        
        return CheckResult(
            check_id='D9',
            check_name='TAN Validation',
            status=CheckStatus.PASS,
            confidence=0.80,
            reasoning='TAN validation requires deductor details. Ensure valid TAN for TDS filing.',
            severity=Severity.MEDIUM
        )
    
    async def _check_d10_section_206ab_higher_rate(self, invoice_data: InvoiceData) -> CheckResult:
        """D10: Section 206AB higher rate applicability"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D10',
                check_name='Section 206AB Higher Rate',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable - Section 206AB not relevant',
                severity=Severity.LOW
            )
        
        # Section 206AB: Higher TDS rate (2x) for non-filers
        # Applies if vendor has not filed IT returns for 2 years
        
        tds_rate = invoice_data.tds_rate or 0
        tds_section = invoice_data.tds_section or '194C'
        
        # Get standard rate
        standard_rate = self.tds_sections.get_rate(tds_section, 'COMPANY', True)
        
        # Check if higher rate applied
        if tds_rate >= standard_rate * 1.8:  # Allow some tolerance
            return CheckResult(
                check_id='D10',
                check_name='Section 206AB Higher Rate',
                status=CheckStatus.WARNING,
                confidence=0.80,
                reasoning=f'Higher TDS rate detected ({tds_rate}% vs standard {standard_rate}%). Verify Section 206AB applicability (non-filer).',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        
        # In production, would check vendor's IT filing status
        return CheckResult(
            check_id='D10',
            check_name='Section 206AB Higher Rate',
            status=CheckStatus.PASS,
            confidence=0.75,
            reasoning=f'Standard rate applied ({tds_rate}%). Section 206AB not applicable (vendor is regular filer).',
            severity=Severity.MEDIUM
        )
    
    async def _check_d11_tds_certificate(self, invoice_data: InvoiceData) -> CheckResult:
        """D11: TDS certificate availability"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D11',
                check_name='TDS Certificate Availability',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable - certificate not required',
                severity=Severity.LOW
            )
        
        tds_amount = invoice_data.tds_amount or 0
        
        if tds_amount > 0:
            # TDS deducted - certificate should be issued (Form 16A)
            return CheckResult(
                check_id='D11',
                check_name='TDS Certificate Availability',
                status=CheckStatus.WARNING,
                confidence=0.70,
                reasoning=f'TDS deducted: ₹{tds_amount:,.2f}. Ensure Form 16A certificate issued to vendor within prescribed time.',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        else:
            return CheckResult(
                check_id='D11',
                check_name='TDS Certificate Availability',
                status=CheckStatus.PASS,
                confidence=0.85,
                reasoning='No TDS deducted - certificate not required',
                severity=Severity.LOW
            )
    
    async def _check_d12_quarterly_reconciliation(self, invoice_data: InvoiceData) -> CheckResult:
        """D12: Quarterly reconciliation flags"""
        
        if not invoice_data.tds_applicable:
            return CheckResult(
                check_id='D12',
                check_name='Quarterly Reconciliation',
                status=CheckStatus.PASS,
                confidence=0.90,
                reasoning='TDS not applicable - reconciliation not required',
                severity=Severity.LOW
            )
        
        invoice_date = invoice_data.invoice_date
        tds_amount = invoice_data.tds_amount or 0
        
        # Determine quarter
        month = invoice_date.month
        if month <= 3:
            quarter = 'Q4'
            due_date = f'{invoice_date.year}-05-31'
        elif month <= 6:
            quarter = 'Q1'
            due_date = f'{invoice_date.year}-07-31'
        elif month <= 9:
            quarter = 'Q2'
            due_date = f'{invoice_date.year}-10-31'
        else:
            quarter = 'Q3'
            due_date = f'{invoice_date.year + 1}-01-31'
        
        if tds_amount > 0:
            return CheckResult(
                check_id='D12',
                check_name='Quarterly Reconciliation',
                status=CheckStatus.WARNING,
                confidence=0.75,
                reasoning=f'Invoice from {quarter} FY{invoice_date.year}. Ensure TDS filed in Form 26Q by {due_date}.',
                severity=Severity.MEDIUM,
                requires_review=True
            )
        else:
            return CheckResult(
                check_id='D12',
                check_name='Quarterly Reconciliation',
                status=CheckStatus.PASS,
                confidence=0.85,
                reasoning=f'Invoice from {quarter} - no TDS to reconcile',
                severity=Severity.LOW
            )
