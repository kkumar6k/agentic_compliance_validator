"""
Orchestrator Agent
Coordinates the entire validation workflow across all validators
"""

import asyncio
from typing import Dict, List
from datetime import datetime
from models.invoice import InvoiceData
from models.validation import ValidationResult, CheckStatus
from validators.arithmetic_validator import ArithmeticValidator
from validators.gst_validator import GSTComplianceValidator
from validators.vendor_validator import VendorValidator
from validators.tds_validator import TDSValidator
from validators.policy_validator import PolicyValidator


class OrchestratorAgent:
    """
    Orchestrator Agent
    
    Coordinates validation workflow:
    1. Extract invoice data (assumed already done)
    2. Run all validators in parallel where possible
    3. Collect results
    4. Determine escalation needs
    5. Generate final report
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # Initialize all validators
        self.arithmetic_validator = ArithmeticValidator(config)
        self.gst_validator = GSTComplianceValidator(config)
        self.vendor_validator = VendorValidator(config)
        self.tds_validator = TDSValidator(config)
        self.policy_validator = PolicyValidator(config)
        
        # Configuration
        self.confidence_threshold = config.get('confidence_threshold', 0.70)
        self.high_value_threshold = config.get('high_value_threshold', 1000000)
    
    async def process_invoice(self, invoice_data: InvoiceData) -> Dict:
        """
        Process complete invoice validation workflow
        
        Returns:
            {
                'status': 'success' | 'failed',
                'validation_result': ValidationResult,
                'escalated': bool,
                'escalation_reasons': List[str],
                'processing_time_ms': float
            }
        """
        
        start_time = datetime.now()
        
        try:
            # Create validation result
            validation_result = ValidationResult(
                invoice_id=invoice_data.invoice_number,
                timestamp=datetime.now()
            )
            
            # Create shared state for validators
            state = {
                'invoice_data': invoice_data,
                'vendor_info': {},
                'escalation_flags': []
            }
            
            # Run all validators in parallel
            print(f"\n🔍 Running validation for: {invoice_data.invoice_number}")
            
            results = await asyncio.gather(
                self.arithmetic_validator.validate(invoice_data, state),
                self.gst_validator.validate(invoice_data, state),
                self.vendor_validator.validate(invoice_data, state),
                self.tds_validator.validate(invoice_data, state),
                self.policy_validator.validate(invoice_data, state),
                return_exceptions=True
            )
            
            # Process results
            category_names = ['C', 'B', 'A', 'D', 'E']
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"   ⚠️  Category {category_names[i]} validation error: {result}")
                    continue
                
                validation_result.category_results[result.category] = result
            
            # Calculate overall statistics
            validation_result = self._calculate_overall_stats(validation_result)
            
            # Determine if escalation needed
            escalated, escalation_reasons = self._should_escalate(
                validation_result, 
                invoice_data
            )
            
            # Calculate processing time
            end_time = datetime.now()
            processing_time_ms = (end_time - start_time).total_seconds() * 1000
            
            return {
                'status': 'success',
                'validation_result': validation_result,
                'escalated': escalated,
                'escalation_reasons': escalation_reasons,
                'processing_time_ms': processing_time_ms
            }
            
        except Exception as e:
            print(f"   ❌ Error processing invoice: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'status': 'failed',
                'error': str(e),
                'validation_result': None,
                'escalated': True,
                'escalation_reasons': [f'Processing error: {str(e)}']
            }
    
    def _calculate_overall_stats(self, validation_result: ValidationResult) -> ValidationResult:
        """Calculate overall statistics across all categories"""
        
        all_checks = []
        for category_result in validation_result.category_results.values():
            all_checks.extend(category_result.checks)
        
        if not all_checks:
            return validation_result
        
        # Count by status
        validation_result.passed_checks = len([c for c in all_checks if c.status == CheckStatus.PASS])
        validation_result.failed_checks = len([c for c in all_checks if c.status == CheckStatus.FAIL])
        validation_result.warnings = len([c for c in all_checks if c.status == CheckStatus.WARNING])
        
        # Calculate average confidence
        confidences = [c.confidence for c in all_checks]
        validation_result.average_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Determine overall status
        if validation_result.failed_checks == 0:
            validation_result.overall_status = 'PASS'
        elif validation_result.failed_checks <= 2 and validation_result.average_confidence > 0.80:
            validation_result.overall_status = 'PASS_WITH_WARNINGS'
        else:
            validation_result.overall_status = 'FAIL'
        
        # Check if review needed
        validation_result.requires_review = any(
            c.requires_review 
            for category in validation_result.category_results.values()
            for c in category.checks
        )
        
        return validation_result
    
    def _should_escalate(self, validation_result: ValidationResult, invoice_data: InvoiceData) -> tuple[bool, List[str]]:
        """
        Determine if invoice should be escalated for human review
        
        Returns:
            (should_escalate, reasons)
        """
        
        reasons = []
        
        # 1. Low confidence
        if validation_result.average_confidence < self.confidence_threshold:
            reasons.append(f'Low confidence: {validation_result.average_confidence:.0%} < {self.confidence_threshold:.0%}')
        
        # 2. High value
        if invoice_data.total_amount > self.high_value_threshold:
            reasons.append(f'High value: ₹{invoice_data.total_amount:,.0f} > ₹{self.high_value_threshold:,.0f}')
        
        # 3. Critical failures
        critical_failures = [
            check
            for category in validation_result.category_results.values()
            for check in category.checks
            if check.status == CheckStatus.FAIL and check.severity.value == 'CRITICAL'
        ]
        
        if critical_failures:
            reasons.append(f'{len(critical_failures)} critical failure(s)')
        
        # 4. Requires review flag
        if validation_result.requires_review:
            review_checks = [
                check
                for category in validation_result.category_results.values()
                for check in category.checks
                if check.requires_review
            ]
            reasons.append(f'{len(review_checks)} check(s) flagged for review')
        
        # 5. Multiple failures
        if validation_result.failed_checks >= 3:
            reasons.append(f'Multiple failures: {validation_result.failed_checks} checks failed')
        
        should_escalate = len(reasons) > 0
        
        return should_escalate, reasons
    
    async def process_batch(self, invoices: List[InvoiceData]) -> Dict:
        """
        Process multiple invoices
        
        Returns summary statistics
        """
        
        print(f"\n📦 Processing batch of {len(invoices)} invoices...\n")
        
        results = []
        for invoice in invoices:
            result = await self.process_invoice(invoice)
            results.append(result)
        
        # Calculate batch statistics
        successful = len([r for r in results if r['status'] == 'success'])
        escalated = len([r for r in results if r.get('escalated', False)])
        
        total_checks = sum([
            len([
                check
                for category in r['validation_result'].category_results.values()
                for check in category.checks
            ])
            for r in results if r['validation_result']
        ])
        
        passed_checks = sum([
            r['validation_result'].passed_checks
            for r in results if r['validation_result']
        ])
        
        avg_confidence = sum([
            r['validation_result'].average_confidence
            for r in results if r['validation_result']
        ]) / len(results) if results else 0
        
        avg_time = sum([
            r.get('processing_time_ms', 0)
            for r in results
        ]) / len(results) if results else 0
        
        return {
            'total_invoices': len(invoices),
            'successful': successful,
            'failed': len(invoices) - successful,
            'escalated': escalated,
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'average_confidence': avg_confidence,
            'average_processing_time_ms': avg_time,
            'results': results
        }
