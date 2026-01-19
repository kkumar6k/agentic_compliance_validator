# Quick Start Guide - Your First Test Case
## Get Your Validator Running in 30 Minutes

This guide walks you through setting up the project and validating your first invoice.

---

## ⚡ 30-Minute Quick Start

### Step 1: Project Setup (5 minutes)

```bash
# 1. Create project directory
mkdir compliance_validator
cd compliance_validator

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Create basic structure
mkdir -p agents validators rag tools models utils data tests

# 4. Save data files
# Copy all uploaded data files to data/ directory:
# - test_invoices.json
# - vendor_registry.json
# - gst_rates_schedule.csv
# - hsn_sac_codes.json
# - tds_sections.json
# - company_policy.yaml
# - historical_decisions.jsonl
```

### Step 2: Install Dependencies (5 minutes)

Create `requirements.txt`:
```txt
# LLM Providers
openai==1.12.0
anthropic==0.18.0

# LangChain
langchain==0.1.10
langchain-openai==0.0.6
langchain-anthropic==0.1.4

# Data Processing
pydantic==2.6.1
python-dotenv==1.0.1
pyyaml==6.0.1
pandas==2.2.0

# Testing
pytest==8.0.0
pytest-asyncio==0.23.5
```

```bash
pip install -r requirements.txt
```

### Step 3: Configuration (5 minutes)

Create `.env`:
```bash
# API Keys
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here

# Models
ORCHESTRATOR_MODEL=gpt-4o-mini
VALIDATOR_MODEL=claude-3-5-sonnet-20241022
```

Create `config.yaml`:
```yaml
models:
  orchestrator: gpt-4o-mini
  validator: claude-3-5-sonnet-20241022
  reporter: gpt-4o-mini

thresholds:
  confidence: 0.70
  high_value: 1000000

data_dir: ./data
```

### Step 4: Minimal Implementation (10 minutes)

Create `models/invoice.py`:
```python
"""Minimal invoice model for testing"""

from pydantic import BaseModel
from typing import List
from datetime import date

class LineItem(BaseModel):
    description: str
    hsn_sac: str
    quantity: float
    rate: float
    amount: float

class InvoiceData(BaseModel):
    invoice_number: str
    invoice_date: date
    seller_gstin: str
    buyer_gstin: str
    line_items: List[LineItem]
    subtotal: float
    cgst_amount: float = 0
    sgst_amount: float = 0
    igst_amount: float = 0
    total_tax: float
    total_amount: float
```

Create `validators/simple_validator.py`:
```python
"""Simple validator for first test"""

from models.invoice import InvoiceData

class SimpleValidator:
    """Validates basic arithmetic"""
    
    def validate(self, invoice: InvoiceData) -> dict:
        """Run basic checks"""
        
        checks = []
        
        # Check 1: Subtotal matches line items
        calculated_subtotal = sum(item.amount for item in invoice.line_items)
        subtotal_match = abs(calculated_subtotal - invoice.subtotal) < 1.0
        
        checks.append({
            'check': 'Subtotal Matches',
            'status': 'PASS' if subtotal_match else 'FAIL',
            'expected': calculated_subtotal,
            'actual': invoice.subtotal
        })
        
        # Check 2: Total tax matches
        calculated_tax = invoice.cgst_amount + invoice.sgst_amount + invoice.igst_amount
        tax_match = abs(calculated_tax - invoice.total_tax) < 1.0
        
        checks.append({
            'check': 'Total Tax Matches',
            'status': 'PASS' if tax_match else 'FAIL',
            'expected': calculated_tax,
            'actual': invoice.total_tax
        })
        
        # Check 3: Total amount
        calculated_total = invoice.subtotal + invoice.total_tax
        total_match = abs(calculated_total - invoice.total_amount) < 1.0
        
        checks.append({
            'check': 'Total Amount Matches',
            'status': 'PASS' if total_match else 'FAIL',
            'expected': calculated_total,
            'actual': invoice.total_amount
        })
        
        # Summary
        passed = sum(1 for c in checks if c['status'] == 'PASS')
        failed = len(checks) - passed
        
        return {
            'checks': checks,
            'passed': passed,
            'failed': failed,
            'overall': 'PASS' if failed == 0 else 'FAIL'
        }
```

### Step 5: Run First Test (5 minutes)

Create `test_first_invoice.py`:
```python
"""Test first invoice"""

import json
from datetime import date
from models.invoice import InvoiceData, LineItem
from validators.simple_validator import SimpleValidator

# Load test invoice
with open('data/test_invoices.json') as f:
    test_invoices = json.load(f)

# Get first invoice (STANDARD_VALID)
invoice_json = test_invoices[0]

# Convert to model
invoice = InvoiceData(
    invoice_number=invoice_json['invoice_number'],
    invoice_date=date.fromisoformat(invoice_json['invoice_date']),
    seller_gstin=invoice_json['vendor']['gstin'],
    buyer_gstin=invoice_json['buyer']['gstin'],
    line_items=[
        LineItem(**item) for item in invoice_json['line_items']
    ],
    subtotal=invoice_json['subtotal'],
    cgst_amount=invoice_json.get('cgst_amount', 0),
    sgst_amount=invoice_json.get('sgst_amount', 0),
    igst_amount=invoice_json.get('igst_amount', 0),
    total_tax=invoice_json['total_tax'],
    total_amount=invoice_json['total_amount']
)

# Validate
validator = SimpleValidator()
result = validator.validate(invoice)

# Display results
print("=" * 80)
print(f"VALIDATION RESULTS: {invoice.invoice_number}")
print("=" * 80)
print()

for check in result['checks']:
    status = "✓" if check['status'] == 'PASS' else "✗"
    print(f"{status} {check['check']:30s}: {check['status']}")
    if check['status'] == 'FAIL':
        print(f"  Expected: {check['expected']}")
        print(f"  Actual:   {check['actual']}")

print()
print(f"Summary: {result['passed']} passed, {result['failed']} failed")
print(f"Overall: {result['overall']}")
print("=" * 80)
```

Run it:
```bash
python test_first_invoice.py
```

**Expected Output:**
```
================================================================================
VALIDATION RESULTS: TS/MH/2024/001234
================================================================================

✓ Subtotal Matches              : PASS
✓ Total Tax Matches             : PASS
✓ Total Amount Matches          : PASS

Summary: 3 passed, 0 failed
Overall: PASS
================================================================================
```

---

## 🎯 Next Steps - Progressive Enhancement

### Phase 1: Add GST Rate Validation (Week 1)

```python
"""validators/gst_validator.py"""

import pandas as pd
from datetime import date

class GSTRateValidator:
    """Validate GST rates"""
    
    def __init__(self):
        # Load GST rate schedule
        self.rates_df = pd.read_csv('data/gst_rates_schedule.csv')
        self.rates_df['effective_from'] = pd.to_datetime(
            self.rates_df['effective_from']
        )
    
    def validate_rate(self, hsn_sac: str, invoice_date: date, applied_rate: float) -> dict:
        """Validate if applied GST rate is correct"""
        
        # Find applicable rate
        matches = self.rates_df[self.rates_df['hsn_sac_code'] == hsn_sac]
        
        if matches.empty:
            return {
                'status': 'WARNING',
                'message': f'HSN/SAC {hsn_sac} not found in schedule'
            }
        
        # Filter by date
        invoice_dt = pd.Timestamp(invoice_date)
        applicable = matches[matches['effective_from'] <= invoice_dt]
        
        if applicable.empty:
            return {
                'status': 'FAIL',
                'message': f'No rate found for {hsn_sac} on {invoice_date}'
            }
        
        # Get most recent rate
        rate_row = applicable.sort_values('effective_from', ascending=False).iloc[0]
        expected_rate = rate_row['rate_igst']  # Assuming interstate
        
        # Compare
        if abs(applied_rate - expected_rate) < 0.1:
            return {
                'status': 'PASS',
                'expected_rate': expected_rate,
                'applied_rate': applied_rate
            }
        else:
            return {
                'status': 'FAIL',
                'expected_rate': expected_rate,
                'applied_rate': applied_rate,
                'message': f'Rate mismatch: expected {expected_rate}%, got {applied_rate}%'
            }

# Usage
gst_validator = GSTRateValidator()
result = gst_validator.validate_rate("998315", date(2024, 9, 15), 18.0)
print(result)
```

### Phase 2: Add Vendor Validation (Week 1-2)

```python
"""validators/vendor_validator.py"""

import json

class VendorValidator:
    """Validate vendor data"""
    
    def __init__(self):
        # Load vendor registry
        with open('data/vendor_registry.json') as f:
            data = json.load(f)
            self.vendors = {v['gstin']: v for v in data['vendors'] if v.get('gstin')}
    
    def validate_vendor(self, gstin: str) -> dict:
        """Validate vendor GSTIN"""
        
        # Check format
        if not self._validate_gstin_format(gstin):
            return {
                'status': 'FAIL',
                'message': 'Invalid GSTIN format'
            }
        
        # Check in registry
        vendor = self.vendors.get(gstin)
        if not vendor:
            return {
                'status': 'WARNING',
                'message': f'Vendor {gstin} not found in registry'
            }
        
        # Check status
        if vendor['status'] != 'ACTIVE':
            return {
                'status': 'FAIL',
                'message': f'Vendor status: {vendor["status"]}',
                'vendor': vendor
            }
        
        return {
            'status': 'PASS',
            'vendor': vendor
        }
    
    def _validate_gstin_format(self, gstin: str) -> bool:
        """Validate GSTIN format"""
        import re
        pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9]{1}[Z]{1}[0-9A-Z]{1}$'
        return bool(re.match(pattern, gstin))

# Usage
vendor_validator = VendorValidator()
result = vendor_validator.validate_vendor("27AABCT1234F1ZP")
print(result)
```

### Phase 3: Add LLM-Based Validation (Week 2-3)

```python
"""validators/llm_validator.py"""

from langchain_anthropic import ChatAnthropic
import json

class LLMValidator:
    """Use LLM for complex validation"""
    
    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            temperature=0
        )
    
    async def validate_hsn_description_match(self, hsn_sac: str, description: str) -> dict:
        """Use LLM to check if description matches HSN code"""
        
        # Load HSN codes
        with open('data/hsn_sac_codes.json') as f:
            codes = json.load(f)
        
        # Get code details
        sac_codes = codes.get('sac_codes', {})
        code_info = sac_codes.get(hsn_sac)
        
        if not code_info:
            return {
                'status': 'WARNING',
                'message': f'HSN/SAC {hsn_sac} not found'
            }
        
        # Query LLM
        prompt = f"""
        Determine if this product/service description matches the HSN/SAC code.
        
        HSN/SAC Code: {hsn_sac}
        Code Description: {code_info['description']}
        Keywords: {', '.join(code_info.get('keywords', []))}
        
        Product Description: {description}
        
        Does the description match the code? Respond in JSON:
        {{
            "matches": true/false,
            "confidence": 0-100,
            "reasoning": "brief explanation"
        }}
        """
        
        response = await self.llm.apredict(prompt)
        
        # Parse response (remove markdown if present)
        response_clean = response.strip()
        if response_clean.startswith('```json'):
            response_clean = response_clean[7:]
        if response_clean.endswith('```'):
            response_clean = response_clean[:-3]
        
        result = json.loads(response_clean.strip())
        
        return {
            'status': 'PASS' if result['matches'] else 'FAIL',
            'confidence': result['confidence'] / 100,
            'reasoning': result['reasoning']
        }

# Usage (async)
import asyncio

async def test_llm():
    validator = LLMValidator()
    result = await validator.validate_hsn_description_match(
        "998315",
        "Software Development Services - CRM Module"
    )
    print(result)

asyncio.run(test_llm())
```

---

## 📈 Development Roadmap

### Week 1: Foundation ✅
- [x] Project setup
- [x] Data models
- [x] Simple arithmetic validation
- [ ] GST rate validation
- [ ] Vendor validation

### Week 2: Core Logic
- [ ] Complete Category C (Arithmetic)
- [ ] Category B basics (GST format checks)
- [ ] Category A basics (Document authenticity)
- [ ] Integration testing

### Week 3: Advanced Logic
- [ ] LLM-based HSN matching
- [ ] Complex GST checks (RCM, composite supply)
- [ ] TDS validation
- [ ] RAG integration

### Week 4: Polish
- [ ] Policy validation
- [ ] Escalation logic
- [ ] Report generation
- [ ] Full test suite

---

## 🐛 Troubleshooting

### Common Issues

**Import Errors**
```bash
# Make sure you're in the venv
source venv/bin/activate

# Reinstall if needed
pip install -r requirements.txt --upgrade
```

**Data File Not Found**
```bash
# Check data directory structure
ls -la data/

# Should see:
# test_invoices.json
# vendor_registry.json
# etc.
```

**API Key Errors**
```bash
# Check .env file exists and has keys
cat .env

# Should see:
# OPENAI_API_KEY=sk-proj-...
# ANTHROPIC_API_KEY=sk-ant-...
```

**Pydantic Validation Errors**
```python
# Add more lenient validation
from pydantic import Field, field_validator

class InvoiceData(BaseModel):
    # Use Optional for fields that might be missing
    irn: Optional[str] = None
    
    # Add validators for complex logic
    @field_validator('total_amount')
    def check_positive(cls, v):
        if v < 0:
            raise ValueError('Amount must be positive')
        return v
```

---

## 🎯 Success Metrics

After completing this quick start:

✅ **You should have:**
- Working project structure
- Validated first test invoice
- Basic arithmetic checks passing
- Foundation for adding more validators

✅ **Next milestones:**
- Add GST rate validation → Test 3 more invoices
- Add vendor validation → Test 5 more invoices
- Add LLM validation → Test edge cases
- Complete all 21 test cases → Achieve 85%+ accuracy

---

## 📚 Resources

**Your Documents:**
- `compliance_validator_architecture.md` - System design
- `implementation_starter_kit.md` - Complete code templates
- `course_to_project_mapping.md` - Apply your learnings
- `testing_framework.md` - Test strategy
- `data_integration_guide.md` - Data access patterns

**Next Steps:**
1. Get first test passing (you just did! 🎉)
2. Add GST validation (use templates)
3. Add more validators incrementally
4. Test on all 21 invoices
5. Refine based on results

**You're now ready to build! 🚀**
