"""
Test First Invoice - Quick Start Script

This script validates the first test invoice using the arithmetic validator.
Run this to verify your setup is working!

Usage:
    python test_first_invoice.py
"""

import asyncio
import json
from datetime import date
from pathlib import Path

from models.invoice import InvoiceData, LineItem
from validators.arithmetic_validator import ArithmeticValidator


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
        return None
    
    return invoice_json


def convert_to_model(invoice_json: dict) -> InvoiceData:
    """Convert JSON to Pydantic model"""
    
    # Convert line items
    line_items = [LineItem(**item) for item in invoice_json['line_items']]
    
    # Create invoice data
    invoice = InvoiceData(
        invoice_number=invoice_json['invoice_number'],
        invoice_date=date.fromisoformat(invoice_json['invoice_date']),
        seller_name=invoice_json['vendor']['name'],
        seller_gstin=invoice_json['vendor']['gstin'],
        buyer_name=invoice_json['buyer']['name'],
        buyer_gstin=invoice_json['buyer']['gstin'],
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
    """Validate invoice using arithmetic validator"""
    
    validator = ArithmeticValidator()
    result = await validator.validate(invoice)
    
    return result


def display_results(invoice: InvoiceData, result):
    """Display validation results"""
    
    print("=" * 80)
    print("COMPLIANCE VALIDATION RESULTS")
    print("=" * 80)
    print()
    print(f"Invoice Number: {invoice.invoice_number}")
    print(f"Date: {invoice.invoice_date}")
    print(f"Amount: ₹{invoice.total_amount:,.2f}")
    print(f"Vendor: {invoice.seller_name}")
    print()
    print("-" * 80)
    print(f"Category: {result.category_name}")
    print("-" * 80)
    print()
    
    for check in result.checks:
        status_symbol = "✓" if check.status.value == "PASS" else "✗"
        status_color = "\033[92m" if check.status.value == "PASS" else "\033[91m"
        reset_color = "\033[0m"
        
        print(f"{status_color}{status_symbol}{reset_color} {check.check_id}: {check.check_name}")
        print(f"  Status: {check.status.value}")
        print(f"  Confidence: {check.confidence:.0%}")
        print(f"  Reasoning: {check.reasoning}")
        print()
    
    print("-" * 80)
    print(f"Summary: {result.passed_count} passed, {result.failed_count} failed")
    print(f"Average Confidence: {result.average_confidence:.0%}")
    
    if result.failed_count == 0:
        print("\n✅ VALIDATION PASSED - All checks successful!")
    else:
        print(f"\n⚠️  VALIDATION FAILED - {result.failed_count} check(s) failed")
    
    print("=" * 80)


async def main():
    """Main execution"""
    
    print()
    print("🚀 Compliance Validator - Quick Start Test")
    print()
    
    # Load test invoice
    print("📄 Loading test invoice...")
    invoice_json = load_test_invoice("INV-2024-0001")
    
    if not invoice_json:
        return
    
    print(f"✓ Loaded: {invoice_json['invoice_id']} - {invoice_json['_test_category']}")
    print()
    
    # Convert to model
    print("🔄 Converting to data model...")
    try:
        invoice = convert_to_model(invoice_json)
        print("✓ Model created successfully")
    except Exception as e:
        print(f"❌ Error creating model: {e}")
        return
    
    print()
    
    # Validate
    print("🔍 Running validation...")
    try:
        result = await validate_invoice(invoice)
        print("✓ Validation complete")
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Display results
    display_results(invoice, result)
    print()
    print("💡 Next Steps:")
    print("   1. Try other test invoices by changing the invoice_id")
    print("   2. Add more validators (GST, TDS, etc.)")
    print("   3. Run the full test suite: pytest tests/")
    print()


if __name__ == "__main__":
    asyncio.run(main())
