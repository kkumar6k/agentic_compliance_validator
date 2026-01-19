"""
Debug script to find where 'name' KeyError occurs
Replace the run command in main_ai.py temporarily with this
"""

import traceback
import json


def debug_invoice_data():
    """Load and inspect invoice data"""

    print("=" * 60)
    print("🔍 DEBUGGING INVOICE DATA")
    print("=" * 60)

    # Load test data
    with open('data/test_invoices.json', 'r') as f:
        invoices = json.load(f)

    invoice = invoices[0]  # INV-2024-0001

    print("\n1️⃣ Original invoice structure:")
    print(f"   - Has 'vendor': {('vendor' in invoice)}")
    print(f"   - Has 'buyer': {('buyer' in invoice)}")
    print(f"   - Has 'seller_name': {('seller_name' in invoice)}")
    print(f"   - Has 'buyer_name': {('buyer_name' in invoice)}")

    if 'vendor' in invoice:
        print(f"   - vendor keys: {list(invoice['vendor'].keys())}")
    if 'buyer' in invoice:
        print(f"   - buyer keys: {list(invoice['buyer'].keys())}")

    # Try transformation
    print("\n2️⃣ Testing transformation:")
    try:
        from utils.data_transformer import transform_invoice_data
        transformed = transform_invoice_data(invoice)
        print("   ✅ Transformation successful!")
        print(f"   - Has 'seller_name': {('seller_name' in transformed)}")
        print(f"   - Has 'buyer_name': {('buyer_name' in transformed)}")
        print(f"   - seller_name value: {transformed.get('seller_name', 'MISSING')}")
        print(f"   - buyer_name value: {transformed.get('buyer_name', 'MISSING')}")
    except Exception as e:
        print(f"   ❌ Transformation failed: {e}")
        traceback.print_exc()

    # Try creating InvoiceData
    print("\n3️⃣ Testing InvoiceData creation:")
    try:
        from models.invoice import InvoiceData, LineItem
        from datetime import date

        line_items = [LineItem(**item) for item in transformed.get("line_items", [])]

        invoice_obj = InvoiceData(
            invoice_number=transformed.get("invoice_number"),
            invoice_date=date.fromisoformat(transformed.get("invoice_date")),
            seller_name=transformed.get("seller_name"),
            seller_gstin=transformed.get("seller_gstin"),
            buyer_name=transformed.get("buyer_name"),
            buyer_gstin=transformed.get("buyer_gstin"),
            line_items=line_items,
            subtotal=transformed.get("subtotal"),
            total_amount=transformed.get("total_amount")
        )
        print("   ✅ InvoiceData created successfully!")
        print(f"   - seller_name: {invoice_obj.seller_name}")
        print(f"   - buyer_name: {invoice_obj.buyer_name}")
    except Exception as e:
        print(f"   ❌ InvoiceData creation failed: {e}")
        traceback.print_exc()

    # Try running workflow
    print("\n4️⃣ Testing workflow initialization:")
    try:
        from agents.langgraph_workflow import ComplianceWorkflow
        workflow = ComplianceWorkflow()
        print("   ✅ Workflow initialized!")
    except Exception as e:
        print(f"   ❌ Workflow initialization failed: {e}")
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("🎯 Debug complete - check output above for errors")
    print("=" * 60)


if __name__ == "__main__":
    debug_invoice_data()