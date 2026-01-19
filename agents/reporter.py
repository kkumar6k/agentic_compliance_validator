"""
Reporter Agent
Generates comprehensive validation reports
"""

import json
from datetime import datetime
from typing import Dict, List
from models.invoice import InvoiceData
from models.validation import ValidationResult, CheckStatus, Severity


class ReporterAgent:
    """
    Reporter Agent
    
    Generates reports in various formats:
    - Console (colored text)
    - JSON (machine readable)
    - Summary (executive view)
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # ANSI color codes
        self.colors = {
            'green': '\033[92m',
            'red': '\033[91m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'gray': '\033[90m',
            'bold': '\033[1m',
            'reset': '\033[0m'
        }
    
    def generate_console_report(
        self, 
        invoice_data: InvoiceData,
        validation_result: ValidationResult,
        escalated: bool = False,
        escalation_reasons: List[str] = None,
        processing_time_ms: float = 0
    ) -> str:
        """Generate detailed console report with colors"""
        
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append(f"{self.colors['bold']}COMPLIANCE VALIDATION REPORT{self.colors['reset']}")
        lines.append("=" * 80)
        lines.append("")
        
        # Invoice details
        lines.append(f"{self.colors['bold']}Invoice Details:{self.colors['reset']}")
        lines.append(f"  Number: {invoice_data.invoice_number}")
        lines.append(f"  Date: {invoice_data.invoice_date}")
        lines.append(f"  Amount: ₹{invoice_data.total_amount:,.2f}")
        lines.append(f"  Vendor: {invoice_data.seller_name}")
        lines.append(f"  GSTIN: {invoice_data.seller_gstin}")
        lines.append("")
        
        # Overall status
        status_color = self._get_status_color(validation_result.overall_status)
        lines.append(f"{self.colors['bold']}Overall Status:{self.colors['reset']} {status_color}{validation_result.overall_status}{self.colors['reset']}")
        lines.append(f"  Total Checks: {validation_result.passed_checks + validation_result.failed_checks + validation_result.warnings}")
        lines.append(f"  Passed: {self.colors['green']}{validation_result.passed_checks}{self.colors['reset']}")
        lines.append(f"  Failed: {self.colors['red']}{validation_result.failed_checks}{self.colors['reset']}")
        lines.append(f"  Warnings: {self.colors['yellow']}{validation_result.warnings}{self.colors['reset']}")
        lines.append(f"  Average Confidence: {validation_result.average_confidence:.0%}")
        lines.append(f"  Processing Time: {processing_time_ms:.0f}ms")
        lines.append("")
        
        # Escalation status
        if escalated:
            lines.append(f"{self.colors['red']}{self.colors['bold']}⚠️  ESCALATION REQUIRED{self.colors['reset']}")
            if escalation_reasons:
                for reason in escalation_reasons:
                    lines.append(f"  • {reason}")
            lines.append("")
        
        # Category results
        for category_id in ['C', 'B', 'A', 'D', 'E']:
            if category_id not in validation_result.category_results:
                continue
            
            category_result = validation_result.category_results[category_id]
            
            lines.append("-" * 80)
            lines.append(f"{self.colors['bold']}Category {category_id}: {category_result.category_name}{self.colors['reset']}")
            lines.append("-" * 80)
            lines.append(f"  Summary: {category_result.passed_count} passed, {category_result.failed_count} failed, {category_result.warning_count} warnings")
            lines.append(f"  Confidence: {category_result.average_confidence:.0%}")
            lines.append("")
            
            # Show all checks
            for check in category_result.checks:
                status_symbol = self._get_status_symbol(check.status)
                status_color = self._get_status_color(check.status.value)
                
                lines.append(f"  {status_color}{status_symbol} {check.check_id}: {check.check_name}{self.colors['reset']}")
                lines.append(f"    Status: {check.status.value} | Confidence: {check.confidence:.0%} | Severity: {check.severity.value}")
                
                if check.requires_review:
                    lines.append(f"    {self.colors['yellow']}⚠️  REQUIRES HUMAN REVIEW{self.colors['reset']}")
                
                # Truncate long reasoning
                reasoning = check.reasoning
                if len(reasoning) > 100:
                    reasoning = reasoning[:97] + "..."
                lines.append(f"    {reasoning}")
                lines.append("")
        
        # Critical issues summary
        critical_issues = self._get_critical_issues(validation_result)
        if critical_issues:
            lines.append("-" * 80)
            lines.append(f"{self.colors['red']}{self.colors['bold']}CRITICAL ISSUES ({len(critical_issues)}){self.colors['reset']}")
            lines.append("-" * 80)
            for issue in critical_issues:
                lines.append(f"  • {issue.check_id}: {issue.check_name}")
                lines.append(f"    {issue.reasoning}")
            lines.append("")
        
        # Footer
        lines.append("=" * 80)
        lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def generate_json_report(
        self,
        invoice_data: InvoiceData,
        validation_result: ValidationResult,
        escalated: bool = False,
        escalation_reasons: List[str] = None
    ) -> str:
        """Generate JSON report"""
        
        report = {
            'invoice': {
                'number': invoice_data.invoice_number,
                'date': str(invoice_data.invoice_date),
                'amount': invoice_data.total_amount,
                'vendor': {
                    'name': invoice_data.seller_name,
                    'gstin': invoice_data.seller_gstin
                }
            },
            'validation': {
                'timestamp': validation_result.timestamp.isoformat(),
                'overall_status': validation_result.overall_status,
                'passed_checks': validation_result.passed_checks,
                'failed_checks': validation_result.failed_checks,
                'warnings': validation_result.warnings,
                'average_confidence': validation_result.average_confidence,
                'requires_review': validation_result.requires_review
            },
            'escalation': {
                'escalated': escalated,
                'reasons': escalation_reasons or []
            },
            'categories': {}
        }
        
        # Add category results
        for category_id, category_result in validation_result.category_results.items():
            report['categories'][category_id] = {
                'name': category_result.category_name,
                'passed': category_result.passed_count,
                'failed': category_result.failed_count,
                'warnings': category_result.warning_count,
                'confidence': category_result.average_confidence,
                'checks': [
                    {
                        'id': check.check_id,
                        'name': check.check_name,
                        'status': check.status.value,
                        'confidence': check.confidence,
                        'severity': check.severity.value,
                        'requires_review': check.requires_review,
                        'reasoning': check.reasoning
                    }
                    for check in category_result.checks
                ]
            }
        
        return json.dumps(report, indent=2)
    
    def generate_summary_report(
        self,
        batch_results: Dict
    ) -> str:
        """Generate executive summary for batch processing"""
        
        lines = []
        
        lines.append("=" * 80)
        lines.append(f"{self.colors['bold']}BATCH VALIDATION SUMMARY{self.colors['reset']}")
        lines.append("=" * 80)
        lines.append("")
        
        lines.append(f"{self.colors['bold']}Overview:{self.colors['reset']}")
        lines.append(f"  Total Invoices: {batch_results['total_invoices']}")
        lines.append(f"  Successful: {self.colors['green']}{batch_results['successful']}{self.colors['reset']}")
        lines.append(f"  Failed: {self.colors['red']}{batch_results['failed']}{self.colors['reset']}")
        lines.append(f"  Escalated: {self.colors['yellow']}{batch_results['escalated']}{self.colors['reset']}")
        lines.append("")
        
        lines.append(f"{self.colors['bold']}Quality Metrics:{self.colors['reset']}")
        lines.append(f"  Total Checks: {batch_results['total_checks']}")
        lines.append(f"  Passed Checks: {batch_results['passed_checks']}")
        
        accuracy = batch_results['passed_checks'] / batch_results['total_checks'] * 100 if batch_results['total_checks'] > 0 else 0
        accuracy_color = self.colors['green'] if accuracy >= 85 else self.colors['yellow'] if accuracy >= 75 else self.colors['red']
        lines.append(f"  Accuracy: {accuracy_color}{accuracy:.1f}%{self.colors['reset']}")
        
        lines.append(f"  Average Confidence: {batch_results['average_confidence']:.0%}")
        lines.append(f"  Average Processing Time: {batch_results['average_processing_time_ms']:.0f}ms")
        lines.append("")
        
        # Success criteria
        lines.append(f"{self.colors['bold']}Success Criteria:{self.colors['reset']}")
        
        if accuracy >= 90:
            lines.append(f"  {self.colors['green']}✓ Excellent (>90% accuracy){self.colors['reset']}")
        elif accuracy >= 85:
            lines.append(f"  {self.colors['green']}✓ Good (>85% accuracy){self.colors['reset']}")
        elif accuracy >= 75:
            lines.append(f"  {self.colors['yellow']}○ Pass (>75% accuracy){self.colors['reset']}")
        else:
            lines.append(f"  {self.colors['red']}✗ Needs Improvement (<75% accuracy){self.colors['reset']}")
        
        escalation_rate = batch_results['escalated'] / batch_results['total_invoices'] * 100 if batch_results['total_invoices'] > 0 else 0
        lines.append(f"  Escalation Rate: {escalation_rate:.1f}%")
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _get_status_symbol(self, status: CheckStatus) -> str:
        """Get status symbol"""
        symbols = {
            CheckStatus.PASS: '✓',
            CheckStatus.FAIL: '✗',
            CheckStatus.WARNING: '⚠',
            CheckStatus.SKIPPED: '○'
        }
        return symbols.get(status, '?')
    
    def _get_status_color(self, status: str) -> str:
        """Get color for status"""
        if status in ['PASS', 'PASS_WITH_WARNINGS']:
            return self.colors['green']
        elif status in ['FAIL', 'CRITICAL']:
            return self.colors['red']
        elif status in ['WARNING', 'MEDIUM']:
            return self.colors['yellow']
        else:
            return self.colors['gray']
    
    def _get_critical_issues(self, validation_result: ValidationResult) -> List:
        """Get all critical issues"""
        issues = []
        
        for category_result in validation_result.category_results.values():
            for check in category_result.checks:
                if check.status == CheckStatus.FAIL and check.severity in [Severity.HIGH, Severity.CRITICAL]:
                    issues.append(check)
        
        return issues
