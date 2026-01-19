# Data Integration Guide
## Working with Challenge Data Files

This guide shows you how to integrate all the challenge data files into your compliance validator system.

---

## 📁 Data Files Overview

```
data/
├── test_invoices.json          # 21 test cases with expected results
├── vendor_registry.json        # 12 vendors with various configurations
├── gst_rates_schedule.csv      # 58 GST rates with temporal validity
├── hsn_sac_codes.json         # 30 HSN/SAC codes with keywords
├── tds_sections.json          # 7 TDS sections with detailed rules
├── company_policy.yaml        # Complex policy with hidden traps
└── historical_decisions.jsonl # 25 past decisions (15% incorrect!)
```

---

## 🔌 Data Loaders

### 1. Test Invoice Loader

```python
"""
utils/data_loaders.py
"""

import json
from typing import List, Dict
from pathlib import Path

class TestInvoiceLoader:
    """Load and manage test invoices"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.invoices = self._load_invoices()
    
    def _load_invoices(self) -> List[Dict]:
        """Load all test invoices"""
        invoice_file = self.data_dir / "test_invoices.json"
        
        with open(invoice_file) as f:
            return json.load(f)
    
    def get_invoice(self, invoice_id: str) -> Dict:
        """Get specific invoice by ID"""
        for inv in self.invoices:
            if inv['invoice_id'] == invoice_id:
                return inv
        raise ValueError(f"Invoice {invoice_id} not found")
    
    def get_by_category(self, category: str) -> List[Dict]:
        """Get invoices by test category"""
        return [
            inv for inv in self.invoices 
            if inv.get('_test_category') == category
        ]
    
    def get_by_complexity(self, complexity: str) -> List[Dict]:
        """Get invoices by complexity level"""
        return [
            inv for inv in self.invoices 
            if inv.get('_complexity') == complexity
        ]
    
    def save_as_files(self, output_dir: str = "data/invoices"):
        """Save each invoice as separate JSON file for testing"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)
        
        for inv in self.invoices:
            invoice_id = inv['invoice_id']
            filename = f"{invoice_id}.json"
            
            with open(output_path / filename, 'w') as f:
                json.dump(inv, f, indent=2)
        
        print(f"Saved {len(self.invoices)} invoices to {output_dir}/")

# Usage
loader = TestInvoiceLoader()
standard_cases = loader.get_by_complexity('LOW')
edge_cases = loader.get_by_complexity('EXTREME')

# Save for testing
loader.save_as_files()
```

### 2. Vendor Registry Loader

```python
class VendorRegistry:
    """Manage vendor data"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.vendors = self._load_vendors()
        self.gstin_index = self._build_gstin_index()
        self.pan_index = self._build_pan_index()
    
    def _load_vendors(self) -> Dict:
        """Load vendor registry"""
        vendor_file = self.data_dir / "vendor_registry.json"
        
        with open(vendor_file) as f:
            data = json.load(f)
            return data['vendors']
    
    def _build_gstin_index(self) -> Dict:
        """Build GSTIN lookup index"""
        return {v['gstin']: v for v in self.vendors if v.get('gstin')}
    
    def _build_pan_index(self) -> Dict:
        """Build PAN lookup index (multiple vendors can have same PAN)"""
        pan_index = {}
        for v in self.vendors:
            pan = v.get('pan')
            if pan:
                if pan not in pan_index:
                    pan_index[pan] = []
                pan_index[pan].append(v)
        return pan_index
    
    def get_by_gstin(self, gstin: str) -> Dict:
        """Get vendor by GSTIN"""
        vendor = self.gstin_index.get(gstin)
        if not vendor:
            raise ValueError(f"Vendor with GSTIN {gstin} not found")
        return vendor
    
    def get_by_pan(self, pan: str) -> List[Dict]:
        """Get vendors by PAN (may return multiple for branches)"""
        vendors = self.pan_index.get(pan, [])
        if not vendors:
            raise ValueError(f"No vendors with PAN {pan} found")
        return vendors
    
    def is_related_party(self, gstin: str) -> bool:
        """Check if vendor is related party (same PAN as another vendor)"""
        try:
            vendor = self.get_by_gstin(gstin)
            pan = vendor.get('pan')
            if pan:
                # Related if multiple vendors share same PAN
                return len(self.pan_index.get(pan, [])) > 1
        except ValueError:
            pass
        return False
    
    def get_tds_section(self, gstin: str) -> str:
        """Get applicable TDS section for vendor"""
        vendor = self.get_by_gstin(gstin)
        return vendor.get('tds_section')
    
    def has_lower_deduction_cert(self, gstin: str) -> bool:
        """Check if vendor has lower deduction certificate"""
        vendor = self.get_by_gstin(gstin)
        cert = vendor.get('lower_deduction_cert')
        
        if not cert:
            return False
        
        # Check validity
        from datetime import datetime
        valid_to = datetime.fromisoformat(cert['valid_to'])
        return valid_to >= datetime.now()
    
    def is_msme(self, gstin: str) -> bool:
        """Check if vendor is MSME registered"""
        vendor = self.get_by_gstin(gstin)
        return vendor.get('msme_registered', False)

# Usage
registry = VendorRegistry()

# Lookup vendor
vendor = registry.get_by_gstin("27AABCT1234F1ZP")
print(f"Vendor: {vendor['legal_name']}")
print(f"TDS Section: {vendor['tds_section']}")

# Check related parties
if registry.is_related_party("29AABCT1234F2ZN"):
    print("⚠️ Related party transaction!")
```

### 3. GST Rates Loader

```python
import pandas as pd
from datetime import date, datetime

class GSTRateSchedule:
    """Manage GST rates with temporal validity"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.rates_df = self._load_rates()
    
    def _load_rates(self) -> pd.DataFrame:
        """Load GST rates schedule"""
        rates_file = self.data_dir / "gst_rates_schedule.csv"
        
        df = pd.read_csv(rates_file)
        
        # Convert dates
        df['effective_from'] = pd.to_datetime(df['effective_from'])
        df['effective_to'] = pd.to_datetime(df['effective_to'])
        
        return df
    
    def get_rate(
        self, 
        hsn_sac: str, 
        invoice_date: date,
        special_conditions: str = None
    ) -> Dict:
        """Get applicable GST rate for date"""
        
        # Filter by HSN/SAC code
        matches = self.rates_df[self.rates_df['hsn_sac_code'] == hsn_sac]
        
        if matches.empty:
            raise ValueError(f"HSN/SAC {hsn_sac} not found in rate schedule")
        
        # Convert invoice_date to datetime for comparison
        invoice_dt = pd.Timestamp(invoice_date)
        
        # Filter by effective date
        applicable = matches[
            (matches['effective_from'] <= invoice_dt) &
            ((matches['effective_to'].isna()) | (matches['effective_to'] >= invoice_dt))
        ]
        
        if applicable.empty:
            # Try to find closest historical rate
            historical = matches[matches['effective_from'] <= invoice_dt]
            if not historical.empty:
                # Use most recent historical rate
                applicable = historical.sort_values('effective_from', ascending=False).head(1)
            else:
                raise ValueError(
                    f"No rate found for HSN/SAC {hsn_sac} on {invoice_date}"
                )
        
        # Handle special conditions (e.g., RCM, SEZ)
        if special_conditions:
            condition_matches = applicable[
                applicable['special_conditions'].str.contains(
                    special_conditions, 
                    case=False, 
                    na=False
                )
            ]
            if not condition_matches.empty:
                applicable = condition_matches
        
        # Return first match (or handle multiple if needed)
        rate_row = applicable.iloc[0]
        
        return {
            'hsn_sac': hsn_sac,
            'description': rate_row['description'],
            'cgst': rate_row['rate_cgst'],
            'sgst': rate_row['rate_sgst'],
            'igst': rate_row['rate_igst'],
            'effective_from': rate_row['effective_from'].date(),
            'effective_to': rate_row['effective_to'].date() if pd.notna(rate_row['effective_to']) else None,
            'special_conditions': rate_row['special_conditions']
        }
    
    def get_rate_changes(self, hsn_sac: str) -> List[Dict]:
        """Get all historical rate changes for HSN/SAC"""
        matches = self.rates_df[self.rates_df['hsn_sac_code'] == hsn_sac]
        
        changes = []
        for _, row in matches.iterrows():
            changes.append({
                'effective_from': row['effective_from'].date(),
                'effective_to': row['effective_to'].date() if pd.notna(row['effective_to']) else None,
                'cgst': row['rate_cgst'],
                'sgst': row['rate_sgst'],
                'igst': row['rate_igst']
            })
        
        return sorted(changes, key=lambda x: x['effective_from'])

# Usage
schedule = GSTRateSchedule()

# Get current rate
rate = schedule.get_rate("998315", date(2024, 9, 15))
print(f"GST Rate for IT Services: {rate['igst']}%")

# Get historical rate (before April 2019 rate change)
old_rate = schedule.get_rate("995411", date(2019, 3, 15))
new_rate = schedule.get_rate("995411", date(2019, 4, 15))
print(f"Construction rate changed from {old_rate['igst']}% to {new_rate['igst']}%")

# Get all rate changes
changes = schedule.get_rate_changes("995411")
for change in changes:
    print(f"From {change['effective_from']}: {change['igst']}%")
```

### 4. HSN/SAC Code Loader

```python
class HSNSACMaster:
    """Manage HSN/SAC codes with semantic search"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.codes = self._load_codes()
    
    def _load_codes(self) -> Dict:
        """Load HSN/SAC codes"""
        codes_file = self.data_dir / "hsn_sac_codes.json"
        
        with open(codes_file) as f:
            return json.load(f)
    
    def get_code(self, code: str) -> Dict:
        """Get HSN/SAC code details"""
        # Try HSN codes first
        hsn = self.codes.get('hsn_codes', {}).get(code)
        if hsn:
            return {**hsn, 'type': 'HSN'}
        
        # Try SAC codes
        sac = self.codes.get('sac_codes', {}).get(code)
        if sac:
            return {**sac, 'type': 'SAC'}
        
        raise ValueError(f"Code {code} not found")
    
    def search_by_keywords(self, keywords: List[str]) -> List[Dict]:
        """Search codes by keywords"""
        results = []
        
        # Search HSN codes
        for code, details in self.codes.get('hsn_codes', {}).items():
            code_keywords = details.get('keywords', [])
            if any(kw.lower() in [ck.lower() for ck in code_keywords] for kw in keywords):
                results.append({
                    'code': code,
                    'type': 'HSN',
                    **details
                })
        
        # Search SAC codes
        for code, details in self.codes.get('sac_codes', {}).items():
            code_keywords = details.get('keywords', [])
            if any(kw.lower() in [ck.lower() for ck in code_keywords] for kw in keywords):
                results.append({
                    'code': code,
                    'type': 'SAC',
                    **details
                })
        
        return results
    
    def validate_description_match(self, code: str, description: str) -> Dict:
        """Check if description matches code"""
        code_details = self.get_code(code)
        keywords = code_details.get('keywords', [])
        
        # Simple keyword matching
        description_lower = description.lower()
        matches = [kw for kw in keywords if kw.lower() in description_lower]
        
        return {
            'code': code,
            'description': description,
            'code_keywords': keywords,
            'matches': matches,
            'match_count': len(matches),
            'likely_match': len(matches) > 0
        }

# Usage
hsn_master = HSNSACMaster()

# Get code details
code = hsn_master.get_code("998315")
print(f"SAC 998315: {code['description']}")
print(f"Keywords: {code['keywords']}")

# Search by keywords
results = hsn_master.search_by_keywords(["software", "development"])
for r in results:
    print(f"{r['code']}: {r['description']}")

# Validate match
match = hsn_master.validate_description_match(
    "998315",
    "Software Development Services - CRM Module"
)
print(f"Match: {match['likely_match']} ({match['match_count']} keywords)")
```

### 5. TDS Sections Loader

```python
class TDSSectionRules:
    """Manage TDS section rules and calculations"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.sections = self._load_sections()
    
    def _load_sections(self) -> Dict:
        """Load TDS sections"""
        sections_file = self.data_dir / "tds_sections.json"
        
        with open(sections_file) as f:
            data = json.load(f)
            # Index by section number
            return {s['section']: s for s in data['tds_sections']}
    
    def get_section(self, section: str) -> Dict:
        """Get section details"""
        return self.sections.get(section)
    
    def get_rate(
        self, 
        section: str, 
        vendor_type: str,
        has_pan: bool = True,
        is_company: bool = False
    ) -> float:
        """Get applicable TDS rate"""
        section_data = self.get_section(section)
        
        if not section_data:
            raise ValueError(f"Section {section} not found")
        
        # No PAN -> higher rate
        if not has_pan:
            return section_data.get('rate_no_pan', 20.0)
        
        # Section-specific logic
        if section == '194C':
            return section_data['rate_company'] if is_company else section_data['rate_individual']
        elif section == '194J':
            # Technical vs Professional
            classification = self._classify_194j_service(vendor_type)
            return section_data.get(f'rate_{classification}', 10.0)
        elif section == '194I':
            # Rent type
            return section_data['sub_sections']['194I_b']['rate']  # Assuming building
        elif section == '194H':
            return section_data['rate']
        elif section == '194Q':
            return section_data['rate']
        else:
            return section_data.get('rate', 0.0)
    
    def _classify_194j_service(self, vendor_type: str) -> str:
        """Classify 194J service as technical or professional"""
        section = self.get_section('194J')
        classification_rules = section.get('classification_rules', {})
        
        it_services = classification_rules.get('IT_SERVICES', {})
        
        # Simple mapping (in production, use LLM for ambiguous cases)
        if 'development' in vendor_type.lower():
            return 'technical'
        elif 'consulting' in vendor_type.lower():
            return 'professional'
        else:
            return 'professional'  # Default
    
    def is_applicable(
        self, 
        section: str, 
        amount: float,
        aggregate_ytd: float = 0
    ) -> bool:
        """Check if TDS is applicable based on thresholds"""
        section_data = self.get_section(section)
        
        if not section_data:
            return False
        
        # Check single payment threshold
        single_threshold = section_data.get('single_payment_threshold')
        if single_threshold and amount < single_threshold:
            return False
        
        # Check aggregate threshold
        aggregate_threshold = section_data.get('aggregate_threshold_per_fy')
        if aggregate_threshold and (aggregate_ytd + amount) < aggregate_threshold:
            return False
        
        # Special thresholds (e.g., 194Q)
        if section == '194Q':
            threshold = section_data.get('threshold', 5000000)
            return (aggregate_ytd + amount) >= threshold
        
        return True
    
    def calculate_tds(
        self,
        section: str,
        base_amount: float,
        vendor_type: str,
        has_pan: bool = True,
        is_company: bool = False,
        apply_206ab: bool = False
    ) -> Dict:
        """Calculate TDS amount"""
        
        rate = self.get_rate(section, vendor_type, has_pan, is_company)
        
        # Apply 206AB if applicable
        if apply_206ab:
            section_206ab = self.sections.get('206AB')
            if section_206ab:
                rate = max(
                    rate * section_206ab['rate_multiplier'],
                    section_206ab['minimum_rate']
                )
        
        tds_amount = base_amount * (rate / 100)
        
        return {
            'section': section,
            'base_amount': base_amount,
            'rate': rate,
            'tds_amount': round(tds_amount, 2),
            '206ab_applied': apply_206ab
        }

# Usage
tds_rules = TDSSectionRules()

# Get rate
rate = tds_rules.get_rate('194J', 'IT_SERVICES', has_pan=True, is_company=True)
print(f"194J rate for IT company: {rate}%")

# Calculate TDS
tds = tds_rules.calculate_tds(
    section='194J',
    base_amount=500000,
    vendor_type='IT_SERVICES',
    has_pan=True,
    is_company=True
)
print(f"TDS: ₹{tds['tds_amount']} @ {tds['rate']}%")

# Check applicability
is_applicable = tds_rules.is_applicable(
    section='194C',
    amount=25000,
    aggregate_ytd=80000
)
print(f"TDS applicable: {is_applicable}")
```

### 6. Company Policy Loader

```python
import yaml

class CompanyPolicy:
    """Manage company policy rules"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.policy = self._load_policy()
    
    def _load_policy(self) -> Dict:
        """Load company policy"""
        policy_file = self.data_dir / "company_policy.yaml"
        
        with open(policy_file) as f:
            return yaml.safe_load(f)
    
    def get_approval_level(
        self, 
        amount: float,
        vendor_gstin: str = None,
        is_first_time: bool = False,
        is_retrospective: bool = False
    ) -> Dict:
        """Determine required approval level"""
        
        # Check special overrides first (hidden complexity!)
        overrides = self.policy.get('_internal_overrides', {})
        
        # Related party check
        if vendor_gstin:
            related_party = overrides.get('related_party_transactions', {})
            if vendor_gstin in related_party.get('vendors', []):
                return {
                    'level': related_party['minimum_approval_level'],
                    'reason': 'Related party transaction',
                    'additional_checks': related_party.get('arm_length_price_check')
                }
        
        # First time vendor
        if is_first_time:
            first_time_rule = self.policy['approval_matrix']['special_overrides']['first_time_vendor']
            return {
                'level': first_time_rule['minimum_level'],
                'reason': 'First-time vendor',
                'additional_checks': first_time_rule['additional_checks']
            }
        
        # Retrospective invoice
        if is_retrospective:
            retro_rule = self.policy['approval_matrix']['special_overrides']['retrospective_invoice']
            return {
                'level': retro_rule['minimum_level'],
                'reason': 'Retrospective invoice',
                'requires_justification': retro_rule['requires_justification']
            }
        
        # Standard approval matrix
        levels = self.policy['approval_matrix']['levels']
        
        for level in levels:
            max_amount = level.get('max_amount')
            if max_amount is None or amount <= max_amount:
                return {
                    'level': level['level'],
                    'name': level['name'],
                    'approvers': level['approvers'],
                    'sla_hours': level.get('sla_hours'),
                    'reason': 'Standard approval process'
                }
        
        # Should not reach here
        return levels[-1]  # Board approval
    
    def check_po_tolerance(self, invoice_amount: float, po_amount: float) -> Dict:
        """Check if invoice is within PO tolerance"""
        rules = self.policy['invoice_acceptance_rules']
        
        tolerance_pct = rules['amount_tolerance_percentage'] / 100
        tolerance_abs = rules['amount_tolerance_absolute']
        
        # Calculate tolerance
        tolerance = max(po_amount * tolerance_pct, tolerance_abs)
        
        lower_limit = po_amount - tolerance
        upper_limit = po_amount + tolerance
        
        within_tolerance = lower_limit <= invoice_amount <= upper_limit
        
        return {
            'within_tolerance': within_tolerance,
            'po_amount': po_amount,
            'invoice_amount': invoice_amount,
            'tolerance_percentage': rules['amount_tolerance_percentage'],
            'tolerance_absolute': tolerance_abs,
            'lower_limit': lower_limit,
            'upper_limit': upper_limit
        }
    
    def check_budget_availability(self, cost_center: str, amount: float) -> Dict:
        """Check budget availability"""
        cost_centers = {
            cc['code']: cc 
            for cc in self.policy['budget_controls']['cost_centers']
        }
        
        cc = cost_centers.get(cost_center)
        if not cc:
            return {'available': False, 'reason': 'Cost center not found'}
        
        budget = cc['annual_budget']
        consumed = cc['consumed_ytd']
        remaining = budget - consumed
        
        alert_threshold = cc['alert_threshold'] / 100
        
        return {
            'available': remaining >= amount,
            'budget': budget,
            'consumed': consumed,
            'remaining': remaining,
            'after_invoice': remaining - amount,
            'utilization_pct': (consumed / budget) * 100,
            'alert_threshold_reached': (consumed / budget) >= alert_threshold,
            'requires_cfo_approval': amount > remaining
        }

# Usage
policy = CompanyPolicy()

# Get approval level
approval = policy.get_approval_level(
    amount=750000,
    is_first_time=False
)
print(f"Approval: Level {approval['level']} - {approval['name']}")

# Check PO tolerance
tolerance = policy.check_po_tolerance(
    invoice_amount=525000,
    po_amount=500000
)
print(f"Within tolerance: {tolerance['within_tolerance']}")

# Check budget
budget = policy.check_budget_availability('CC001', 5000000)
print(f"Budget available: {budget['available']}")
print(f"Utilization: {budget['utilization_pct']:.1f}%")
```

### 7. Historical Decisions Loader

```python
class HistoricalDecisions:
    """Manage historical decisions with correctness flags"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.decisions = self._load_decisions()
    
    def _load_decisions(self) -> List[Dict]:
        """Load historical decisions"""
        decisions_file = self.data_dir / "historical_decisions.jsonl"
        
        decisions = []
        with open(decisions_file) as f:
            for line in f:
                decisions.append(json.loads(line))
        
        return decisions
    
    def get_correct_decisions(self) -> List[Dict]:
        """Get only correct decisions"""
        return [d for d in self.decisions if d.get('correct', True)]
    
    def get_incorrect_decisions(self) -> List[Dict]:
        """Get incorrect decisions for learning"""
        return [d for d in self.decisions if not d.get('correct', True)]
    
    def find_similar(
        self, 
        vendor_gstin: str = None,
        amount_range: tuple = None,
        tds_section: str = None
    ) -> List[Dict]:
        """Find similar historical cases"""
        
        results = self.decisions.copy()
        
        if vendor_gstin:
            results = [d for d in results if d.get('vendor_gstin') == vendor_gstin]
        
        if amount_range:
            min_amt, max_amt = amount_range
            results = [
                d for d in results 
                if min_amt <= d.get('invoice_amount', 0) <= max_amt
            ]
        
        if tds_section:
            results = [d for d in results if d.get('tds_section') == tds_section]
        
        return results
    
    def analyze_error_patterns(self) -> Dict:
        """Analyze common errors in historical decisions"""
        
        incorrect = self.get_incorrect_decisions()
        
        error_types = {}
        for dec in incorrect:
            error = dec.get('_error', 'Unknown error')
            error_types[error] = error_types.get(error, 0) + 1
        
        return {
            'total_decisions': len(self.decisions),
            'incorrect_count': len(incorrect),
            'error_rate': len(incorrect) / len(self.decisions),
            'error_types': error_types
        }

# Usage
historical = HistoricalDecisions()

# Get correct vs incorrect
correct = historical.get_correct_decisions()
incorrect = historical.get_incorrect_decisions()
print(f"Correct: {len(correct)}, Incorrect: {len(incorrect)}")

# Find similar cases
similar = historical.find_similar(
    vendor_gstin="07AABCG5678H1Z9",
    tds_section="194C"
)
print(f"Found {len(similar)} similar cases")

# Analyze errors
errors = historical.analyze_error_patterns()
print(f"Error rate: {errors['error_rate']:.1%}")
print("Common errors:")
for error, count in errors['error_types'].items():
    print(f"  - {error}: {count}")
```

---

## 🎯 Integration Example

### Complete Data Layer

```python
"""
data_layer.py
Unified data access layer
"""

class DataLayer:
    """Unified access to all challenge data"""
    
    def __init__(self, data_dir: str = "data"):
        self.test_invoices = TestInvoiceLoader(data_dir)
        self.vendors = VendorRegistry(data_dir)
        self.gst_rates = GSTRateSchedule(data_dir)
        self.hsn_codes = HSNSACMaster(data_dir)
        self.tds_sections = TDSSectionRules(data_dir)
        self.policy = CompanyPolicy(data_dir)
        self.historical = HistoricalDecisions(data_dir)
    
    def validate_invoice(self, invoice_data: Dict) -> Dict:
        """Complete validation using all data sources"""
        
        results = {}
        
        # Vendor validation
        try:
            vendor = self.vendors.get_by_gstin(invoice_data['vendor']['gstin'])
            results['vendor'] = {
                'found': True,
                'status': vendor['status'],
                'tds_section': vendor.get('tds_section'),
                'is_msme': vendor.get('msme_registered')
            }
        except ValueError as e:
            results['vendor'] = {'found': False, 'error': str(e)}
        
        # GST rate validation
        for item in invoice_data.get('line_items', []):
            try:
                rate = self.gst_rates.get_rate(
                    item['hsn_sac'],
                    date.fromisoformat(invoice_data['invoice_date'])
                )
                results[f"gst_rate_{item['hsn_sac']}"] = rate
            except ValueError as e:
                results[f"gst_rate_{item['hsn_sac']}"] = {'error': str(e)}
        
        # Approval level
        approval = self.policy.get_approval_level(
            invoice_data['total_amount']
        )
        results['approval'] = approval
        
        return results

# Usage
data = DataLayer()

# Load test invoice
invoice = data.test_invoices.get_invoice('INV-2024-0001')

# Validate
results = data.validate_invoice(invoice)
print(json.dumps(results, indent=2, default=str))
```

---

## 📚 Next Steps

1. **Create data loaders** - implement the classes above
2. **Test data access** - verify all files load correctly
3. **Integrate with agents** - pass data to validators
4. **Run test cases** - validate on all 21 invoices

**All your reference data is now accessible! 🎯**
