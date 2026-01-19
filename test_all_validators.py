"""
Test All Validators - Comprehensive Test Script

This script validates an invoice using all available validators:
- Arithmetic (Category C)
- GST Compliance (Category B)
- Vendor Validation (Category A partial)

Usage:
    python test_all_validators.py [invoice_id]
    
    Default: INV-2024-0001
    Example: python test_all_validators.py INV-2024-0002
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from models.invoice import InvoiceData, LineItem
from validators.arithmetic_validator import ArithmeticValidator
from validators.gst_validator import GSTComplianceValidator
from validators.vendor_validator import VendorValidator


def load_test_invoice(invoice_id: str = "INV-2024-0001"):
    """Load test invoice from JSON"""
    
    data_file = Path("data/test_invoices.json")
    
    if not data_file.exists():
        print(f"❌ Error: {data_file} not found!")
        print("Make sure you're running this from the project root directory.")
        return None
    
    with open(data_file) as f:
        invoices = json.load(f)
    
    # Find the invoice
    invoice_json = None
    for inv in invoices:
        if inv['invoice_id'] == invoice_id:
            invoice_json = inv
            break
    
    if not invoice_json:
        print(f"❌ Error: Invoice {invoice_id} not found!")
        print(f"Available invoices: {[inv['invoice_id'] for inv in invoices[:5]]}...")
        return None
    
    return invoice_json


def convert_to_model(invoice_json: dict) -> InvoiceData:
    """Convert JSON to Pydantic model"""
    
    # Convert line items
    line_items = [LineItem(**item) for item in invoice_json['line_items']]
    
    # Determine seller state from GSTIN
    seller_state_code = invoice_json['vendor']['gstin'][:2]
    state_map = {
        '27': 'Maharashtra',
        '07': 'Delhi',
        '29': 'Karnataka',
        '33': 'Tamil Nadu',
        '09': 'Uttar Pradesh'
    }
    seller_state = state_map.get(seller_state_code, None)
    
    # Determine buyer state
    buyer_state_code = invoice_json['buyer']['gstin'][:2]
    buyer_state = state_map.get(buyer_state_code, None)
    
    # Create invoice data
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
        total_tax=invoice_json['total_tax'],
        total_amount=invoice_json['total_amount'],
        irn=invoice_json.get('irn'),
        qr_code_present=invoice_json.get('qr_code_present', False),
        payment_terms=invoice_json.get('payment_terms'),
        po_reference=invoice_json.get('po_reference'),
        notes=invoice_json.get('notes')
    )
    
    return invoice


async def validate_invoice(invoice: InvoiceData):
    """Validate invoice using all validators"""
    
    results = {}
    
    # Arithmetic validation
    print("  Running arithmetic checks...")
    arithmetic_validator = ArithmeticValidator()
    results['arithmetic'] = await arithmetic_validator.validate(invoice)
    
    # GST validation
    print("  Running GST compliance checks...")
    gst_validator = GSTComplianceValidator()
    results['gst'] = await gst_validator.validate(invoice)
    
    # Vendor validation
    print("  Running vendor checks...")
    vendor_validator = VendorValidator()
    results['vendor'] = await vendor_validator.validate(invoice)
    
    return results


def display_results(invoice: InvoiceData, invoice_json: dict, results: dict):
    """Display validation results"""
    
    print()
    print("=" * 80)
    print("COMPREHENSIVE COMPLIANCE VALIDATION RESULTS")
    print("=" * 80)
    print()
    print(f"Invoice Number: {invoice.invoice_number}")
    print(f"Date: {invoice.invoice_date}")
    print(f"Amount: ₹{invoice.total_amount:,.2f}")
    print(f"Vendor: {invoice.seller_name}")
    print()
    print(f"Test Category: {invoice_json.get('_test_category', 'N/A')}")
    print(f"Complexity: {invoice_json.get('_complexity', 'N/A')}")
    print(f"Expected Result: {invoice_json.get('_expected_result', 'N/A')}")
    print()
    
    # Display each category
    total_passed = 0
    total_failed = 0
    total_warnings = 0
    all_checks = []
    
    for category_name, result in results.items():
        print("-" * 80)
        print(f"Category: {result.category_name}")
        print("-" * 80)
        print()
        
        for check in result.checks:
            status_symbol = {
                'PASS': '✓',
                'FAIL': '✗',
                'WARNING': '⚠',
                'SKIPPED': '○'
            }.get(check.status.value, '?')
            
            status_color = {
                'PASS': "\033[92m",    # Green
                'FAIL': "\033[91m",    # Red
                'WARNING': "\033[93m", # Yellow
                'SKIPPED': "\033[90m"  # Gray
            }.get(check.status.value, "")
            reset_color = "\033[0m"
            
            print(f"{status_color}{status_symbol}{reset_color} {check.check_id}: {check.check_name}")
            print(f"  Status: {check.status.value}")
            print(f"  Confidence: {check.confidence:.0%}")
            if check.requires_review:
                print(f"  ⚠️  REQUIRES HUMAN REVIEW")
            print(f"  {check.reasoning[:100]}{'...' if len(check.reasoning) > 100 else ''}")
            print()
            
            all_checks.append(check)
        
        total_passed += result.passed_count
        total_failed += result.failed_count
        total_warnings += result.warning_count
        
        print(f"Category Summary: {result.passed_count} passed, {result.failed_count} failed, {result.warning_count} warnings")
        print()
    
    # Overall summary
    print("-" * 80)
    print("OVERALL SUMMARY")
    print("-" * 80)
    print(f"Total Checks: {len(all_checks)}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Warnings: {total_warnings}")
    
    # Calculate average confidence
    avg_confidence = sum(c.confidence for c in all_checks) / len(all_checks) if all_checks else 0
    print(f"Average Confidence: {avg_confidence:.0%}")
    
    # Determine overall status
    if total_failed == 0:
        print("\n✅ VALIDATION PASSED - All critical checks successful!")
        if total_warnings > 0:
            print(f"   Note: {total_warnings} warning(s) for review")
    else:
        print(f"\n⚠️  VALIDATION ISSUES - {total_failed} check(s) failed")
        
        # List critical failures
        critical_failures = [c for c in all_checks if c.status.value == 'FAIL' and c.severity.value in ['HIGH', 'CRITICAL']]
        if critical_failures:
            print(f"   Critical failures: {len(critical_failures)}")
    
    # Check for required reviews
    reviews_needed = [c for c in all_checks if c.requires_review]
    if reviews_needed:
        print(f"\n🔍 HUMAN REVIEW REQUIRED: {len(reviews_needed)} check(s) flagged")
    
    print("=" * 80)


async def main():
    """Main execution"""
    
    # Get invoice ID from command line or use default
    invoice_id = sys.argv[1] if len(sys.argv) > 1 else "INV-2024-0001"
    
    print()
    print("🚀 Compliance Validator - Comprehensive Test")
    print()
    
    # Load test invoice
    print(f"📄 Loading invoice: {invoice_id}")
    invoice_json = load_test_invoice(invoice_id)
    
    if not invoice_json:
        return
    
    print(f"✓ Loaded: {invoice_json['_test_category']}")
    print()
    
    # Convert to model
    print("🔄 Converting to data model...")
    try:
        invoice = convert_to_model(invoice_json)
        print("✓ Model created successfully")
    except Exception as e:
        print(f"❌ Error creating model: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Validate
    print("🔍 Running all validators...")
    try:
        results = await validate_invoice(invoice)
        print("✓ Validation complete")
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Display results
    display_results(invoice, invoice_json, results)
    
    print()
    print("💡 Try Other Invoices:")
    print("   python test_all_validators.py INV-2024-0002  # Transport with RCM")
    print("   python test_all_validators.py INV-2024-0847  # The famous edge case!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
