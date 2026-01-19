"""
Verification script to check if data transformer is properly installed
Run this BEFORE running main_ai.py
"""

import sys
import os

print("🔍 Checking Installation...")
print("=" * 60)

# Check 1: Transformer file exists
transformer_path = "utils/data_transformer.py"
if os.path.exists(transformer_path):
    print("✅ data_transformer.py found in utils/")
else:
    print(f"❌ data_transformer.py NOT FOUND in utils/")
    print(f"   Please copy data_transformer.py to utils/data_transformer.py")
    sys.exit(1)

# Check 2: Workflow file has import
workflow_path = "agents/langgraph_workflow.py"
if os.path.exists(workflow_path):
    with open(workflow_path, 'r') as f:
        content = f.read()

        if "from utils.data_transformer import transform_invoice_data" in content:
            print("✅ langgraph_workflow.py has transformer import")
        else:
            print("❌ langgraph_workflow.py MISSING transformer import")
            print("   Please replace agents/langgraph_workflow.py with new version")
            sys.exit(1)

        # Count transform calls
        count = content.count("transform_invoice_data(state[")
        if count >= 6:
            print(f"✅ Found {count} transform calls in workflow (expected 6)")
        else:
            print(f"❌ Only found {count} transform calls (expected 6)")
            print("   Please replace agents/langgraph_workflow.py with new version")
            sys.exit(1)
else:
    print("❌ langgraph_workflow.py NOT FOUND")
    sys.exit(1)

# Check 3: All validators exist
validators = [
    ("validators/document_validator.py", "DocumentValidator"),
    ("validators/gst_validator.py", "GSTValidator"),
    ("validators/tds_validator.py", "TDSValidator"),
]

for path, name in validators:
    if os.path.exists(path):
        print(f"✅ {name} found")
    else:
        print(f"⚠️  {name} not found at {path}")

print("=" * 60)
print("✅ Installation verified! Ready to run main_ai.py")
print()
print("Run: python main_ai.py INV-2024-0001")