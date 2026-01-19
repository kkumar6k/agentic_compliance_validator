"""
Main Compliance Validator
Complete invoice validation system

Usage:
    python main.py [invoice_id]                    # Validate single invoice
    python main.py --batch                         # Validate all test invoices
    python main.py --complexity LOW                # Validate by complexity
    python main.py --category STANDARD_VALID       # Validate by category
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import date

from models.invoice import InvoiceData, LineItem
from agents.orchestrator import OrchestratorAgent
from agents.reporter import ReporterAgent
from utils.data_loaders import InvoiceDataLoader


class ComplianceValidator:
    """Main compliance validator application"""
    
    def __init__(self, config_path: str = "config.yaml"):
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize agents
        self.orchestrator = OrchestratorAgent(self.config)
        self.reporter = ReporterAgent(self.config)
        
        # Initialize data loader
        self.invoice_loader = InvoiceDataLoader()
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration"""
        import yaml
        
        try:
            with open(config_path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"⚠️  Config file {config_path} not found, using defaults")
            return {
                'confidence_threshold': 0.70,
                'high_value_threshold': 1000000
            }
    
    def convert_json_to_model(self, invoice_json: dict) -> InvoiceData:
        """Convert JSON invoice to data model"""
        
        # Convert line items
        line_items = [LineItem(**item) for item in invoice_json['line_items']]
        
        # Determine states from GSTIN
        state_map = {
            '01': 'Jammu and Kashmir', '02': 'Himachal Pradesh', '03': 'Punjab',
            '04': 'Chandigarh', '05': 'Uttarakhand', '06': 'Haryana',
            '07': 'Delhi', '08': 'Rajasthan', '09': 'Uttar Pradesh',
            '10': 'Bihar', '27': 'Maharashtra', '29': 'Karnataka', '33': 'Tamil Nadu'
        }
        
        seller_state_code = invoice_json['vendor']['gstin'][:2]
        buyer_state_code = invoice_json['buyer']['gstin'][:2]
        
        seller_state = state_map.get(seller_state_code)
        buyer_state = state_map.get(buyer_state_code)
        
        # Create invoice data model
        invoice = InvoiceData(
            invoice_number=invoice_json['invoice_number'],
            invoice_date=date.fromisoformat(invoice_json['invoice_date']),
            seller_name=invoice_json['vendor']['name'],
            seller_gstin=invoice_json['vendor']['gstin'],
            seller_address=invoice_json['vendor'].get('address'),
            seller_state=seller_state,
            buyer_name=invoice_json['buyer']['name'],
            buyer_gstin=invoice_json['buyer']['gstin'],
            buyer_address=invoice_json['buyer'].get('address'),
            buyer_state=buyer_state,
            line_items=line_items,
            subtotal=invoice_json['subtotal'],
            cgst_amount=invoice_json.get('cgst_amount', 0),
            sgst_amount=invoice_json.get('sgst_amount', 0),
            igst_amount=invoice_json.get('igst_amount', 0),
            cess=invoice_json.get('cess', 0),
            total_tax=invoice_json['total_tax'],
            total_amount=invoice_json['total_amount'],
            irn=invoice_json.get('irn'),
            qr_code_present=invoice_json.get('qr_code_present', False),
            reverse_charge=invoice_json.get('reverse_charge', False),
            tds_applicable=invoice_json.get('tds_applicable', False),
            tds_section=invoice_json.get('tds_section'),
            tds_rate=invoice_json.get('tds_rate'),
            tds_amount=invoice_json.get('tds_amount'),
            po_reference=invoice_json.get('po_reference'),
            payment_terms=invoice_json.get('payment_terms'),
            notes=invoice_json.get('notes')
        )
        
        return invoice
    
    async def validate_single(self, invoice_id: str):
        """Validate a single invoice"""
        
        print("\n🚀 Compliance Validator - Single Invoice Mode")
        print("=" * 80)
        
        # Load invoice
        try:
            invoice_json = self.invoice_loader.get_invoice(invoice_id)
        except ValueError as e:
            print(f"❌ Error: {e}")
            return
        
        print(f"\n📄 Loading invoice: {invoice_id}")
        print(f"   Category: {invoice_json.get('_test_category', 'N/A')}")
        print(f"   Complexity: {invoice_json.get('_complexity', 'N/A')}")
        
        # Convert to model
        invoice_data = self.convert_json_to_model(invoice_json)
        
        # Process
        result = await self.orchestrator.process_invoice(invoice_data)
        
        # Generate report
        if result['status'] == 'success':
            report = self.reporter.generate_console_report(
                invoice_data,
                result['validation_result'],
                result['escalated'],
                result['escalation_reasons'],
                result['processing_time_ms']
            )
            print("\n" + report)
            
            # Save JSON report
            json_report = self.reporter.generate_json_report(
                invoice_data,
                result['validation_result'],
                result['escalated'],
                result['escalation_reasons']
            )
            
            report_file = Path("reports") / f"{invoice_id}_report.json"
            report_file.parent.mkdir(exist_ok=True)
            with open(report_file, 'w') as f:
                f.write(json_report)
            
            print(f"\n💾 JSON report saved: {report_file}")
        else:
            print(f"\n❌ Validation failed: {result.get('error')}")
    
    async def validate_batch(self, filter_complexity: str = None, filter_category: str = None):
        """Validate multiple invoices"""
        
        print("\n🚀 Compliance Validator - Batch Mode")
        print("=" * 80)
        
        # Load invoices
        if filter_complexity:
            invoices_json = self.invoice_loader.get_by_complexity(filter_complexity)
            print(f"\n📦 Processing {len(invoices_json)} invoices with complexity: {filter_complexity}")
        elif filter_category:
            invoices_json = self.invoice_loader.get_by_category(filter_category)
            print(f"\n📦 Processing {len(invoices_json)} invoices in category: {filter_category}")
        else:
            invoices_json = self.invoice_loader.invoices
            print(f"\n📦 Processing all {len(invoices_json)} test invoices")
        
        # Convert to models
        invoices_data = []
        for inv_json in invoices_json:
            try:
                inv_data = self.convert_json_to_model(inv_json)
                invoices_data.append(inv_data)
            except Exception as e:
                print(f"   ⚠️  Error converting {inv_json['invoice_id']}: {e}")
        
        # Process batch
        batch_results = await self.orchestrator.process_batch(invoices_data)
        
        # Generate summary
        summary = self.reporter.generate_summary_report(batch_results)
        print("\n" + summary)
        
        # Show individual results
        print("\n" + "=" * 80)
        print("INDIVIDUAL RESULTS")
        print("=" * 80)
        
        for i, result in enumerate(batch_results['results']):
            if result['status'] == 'success':
                inv_data = invoices_data[i]
                val_result = result['validation_result']
                
                status_symbol = '✓' if val_result.overall_status == 'PASS' else '✗' if val_result.overall_status == 'FAIL' else '○'
                escalation_flag = ' 🚨' if result['escalated'] else ''
                
                print(f"{status_symbol} {inv_data.invoice_number:20s} | "
                      f"{val_result.overall_status:20s} | "
                      f"Conf: {val_result.average_confidence:>5.0%} | "
                      f"P:{val_result.passed_checks:2d} F:{val_result.failed_checks:2d} W:{val_result.warnings:2d}"
                      f"{escalation_flag}")
        
        print("=" * 80)
        
        # Save batch report
        batch_report_file = Path("reports") / "batch_report.json"
        batch_report_file.parent.mkdir(exist_ok=True)
        with open(batch_report_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_invoices': batch_results['total_invoices'],
                    'successful': batch_results['successful'],
                    'failed': batch_results['failed'],
                    'escalated': batch_results['escalated'],
                    'accuracy': batch_results['passed_checks'] / batch_results['total_checks'] * 100 if batch_results['total_checks'] > 0 else 0
                },
                'invoices': [
                    {
                        'invoice_number': invoices_data[i].invoice_number,
                        'status': result['validation_result'].overall_status if result['status'] == 'success' else 'ERROR',
                        'escalated': result.get('escalated', False)
                    }
                    for i, result in enumerate(batch_results['results'])
                ]
            }, f, indent=2)
        
        print(f"\n💾 Batch report saved: {batch_report_file}")


async def main():
    """Main entry point"""
    
    validator = ComplianceValidator()
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == '--batch':
            await validator.validate_batch()
        elif arg == '--complexity' and len(sys.argv) > 2:
            await validator.validate_batch(filter_complexity=sys.argv[2])
        elif arg == '--category' and len(sys.argv) > 2:
            await validator.validate_batch(filter_category=sys.argv[2])
        elif arg == '--help':
            print("""
Compliance Validator - Usage

Single Invoice:
    python main.py [invoice_id]
    Example: python main.py INV-2024-0001

Batch Processing:
    python main.py --batch                      # All invoices
    python main.py --complexity LOW             # By complexity
    python main.py --category STANDARD_VALID    # By test category

Options:
    --help          Show this help message
""")
        else:
            # Treat as invoice ID
            await validator.validate_single(arg)
    else:
        # Default: validate first invoice
        await validator.validate_single("INV-2024-0001")


if __name__ == "__main__":
    asyncio.run(main())
