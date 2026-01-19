# Compliance Validator - Testing & Data Analysis Guide
## Working with Real Test Data

This guide provides practical frameworks for testing your compliance validator using the actual challenge data.

---

## 📊 Test Data Overview

### Test Invoices: 21 Cases

**Distribution by Complexity:**
- **Low (2)**: Standard valid invoices - should pass all checks
- **Medium (8)**: Single complicating factor (wrong rate, interstate, etc.)
- **High (8)**: Multiple complications (RCM, composition scheme, etc.)
- **Very High (2)**: Advanced scenarios requiring deep reasoning
- **Extreme (1)**: The famous INV-2024-0847 - composite supply nightmare

**Test Categories:**
```
Standard Cases:
├─ STANDARD_VALID
├─ INTERSTATE_SERVICES
└─ MIXED_GST_RATES

GST Complexity:
├─ WRONG_GST_RATE
├─ COMPOSITION_SCHEME
├─ COMPOSITION_HIGH_VALUE
├─ GTA_RCM
├─ INTERSTATE_GTA
└─ COMPOSITE_SUPPLY_NIGHTMARE (⚠️ extreme)

TDS Complexity:
├─ RENT_TDS_ON_GST
├─ 206AB_APPLICABLE
└─ FOREIGN_VENDOR_RCM

Vendor Issues:
├─ SUSPENDED_VENDOR
└─ RELATED_PARTY_BRANCH

Policy Issues:
├─ HIGH_VALUE_APPROVAL
├─ FY_BOUNDARY
└─ GOODS_ABOVE_5CR_THRESHOLD

Data Quality:
├─ DATA_QUALITY_ISSUES
├─ DUPLICATE_INVOICE
└─ CREDIT_NOTE

Special Cases:
└─ EXPORT_INVOICE
```

### Historical Decisions: 25 Records
- **Correct decisions**: ~85% (21 records)
- **Incorrect decisions**: ~15% (4 records with `"correct": false`)
- Use these to test that your agent doesn't blindly copy wrong patterns!

### Reference Data:
- **GST Rates**: 58 entries with temporal validity
- **HSN/SAC Codes**: 15 goods + 15 services with keywords
- **TDS Sections**: 7 sections with detailed rules
- **Vendors**: 12 vendors with various types
- **Company Policy**: Complex approval matrix with hidden overrides

---

## 🧪 Testing Framework

### Phase 1: Unit Testing (Week 1-2)

Test individual components in isolation.

```python
"""
tests/test_extractor.py
Unit tests for data extraction
"""

import pytest
import json
from agents.extractor import ExtractorAgent
from models.invoice import InvoiceData

class TestExtractorAgent:
    """Test invoice extraction"""
    
    @pytest.fixture
    def extractor(self):
        config = {'extractor_model': 'gpt-4o-mini'}
        return ExtractorAgent(config)
    
    @pytest.fixture
    def test_invoices(self):
        with open('data/test_invoices.json') as f:
            return json.load(f)
    
    def test_extract_standard_invoice(self, extractor, test_invoices):
        """Test extraction of standard valid invoice"""
        
        # Get first test invoice (STANDARD_VALID)
        invoice_json = test_invoices[0]
        
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invoice_json, f)
            temp_path = f.name
        
        # Extract
        result = await extractor.extract(temp_path, None)
        
        # Assertions
        assert result.confidence > 0.9
        assert result.data.invoice_number == "TS/MH/2024/001234"
        assert result.data.total_amount == 590000
        assert result.data.seller_gstin == "27AABCT1234F1ZP"
        
        # Cleanup
        import os
        os.remove(temp_path)
    
    def test_extract_data_quality_issues(self, extractor, test_invoices):
        """Test handling of data quality issues"""
        
        # Get invoice with data quality issues
        invoice_json = next(
            inv for inv in test_invoices 
            if inv['_test_category'] == 'DATA_QUALITY_ISSUES'
        )
        
        # This should handle gracefully
        # May have lower confidence or warnings
        result = await extractor.extract(...)
        
        assert result.confidence < 1.0  # Should flag quality issues
        assert len(result.warnings) > 0
```

### Phase 2: Integration Testing (Week 3-4)

Test complete workflows with real test data.

```python
"""
tests/test_integration.py
Integration tests with test invoices
"""

import pytest
import json
from agents.orchestrator import OrchestratorAgent

class TestComplianceValidation:
    """Test complete validation workflow"""
    
    @pytest.fixture
    def orchestrator(self):
        config = {
            'orchestrator_model': 'gpt-4o-mini',
            'validator_model': 'claude-3-5-sonnet-20241022',
            'resolver_model': 'claude-3-5-sonnet-20241022',
            'reporter_model': 'gpt-4o-mini',
            'confidence_threshold': 0.70,
            'high_value_threshold': 1000000
        }
        return OrchestratorAgent(config)
    
    @pytest.fixture
    def test_invoices(self):
        with open('data/test_invoices.json') as f:
            return json.load(f)
    
    @pytest.mark.asyncio
    async def test_standard_valid_invoice(self, orchestrator, test_invoices):
        """Test: Standard valid invoice should PASS"""
        
        invoice = next(
            inv for inv in test_invoices 
            if inv['_test_category'] == 'STANDARD_VALID'
        )
        
        result = await orchestrator.process_invoice(invoice)
        
        # Should pass all checks
        assert result['status'] == 'success'
        assert result['report'].overall_status == 'PASS'
        assert result['report'].failed_checks == 0
        assert not result['escalated']
    
    @pytest.mark.asyncio
    async def test_wrong_gst_rate(self, orchestrator, test_invoices):
        """Test: Wrong GST rate should FAIL B6 check"""
        
        invoice = next(
            inv for inv in test_invoices 
            if inv['_test_category'] == 'WRONG_GST_RATE'
        )
        
        result = await orchestrator.process_invoice(invoice)
        
        # Should fail GST rate check
        assert result['report'].overall_status == 'FAIL'
        
        # Find B6 check result
        gst_category = result['report'].category_results['B']
        b6_check = next(c for c in gst_category.checks if c.check_id == 'B6')
        
        assert b6_check.status == 'FAIL'
        assert 'rate' in b6_check.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_suspended_vendor(self, orchestrator, test_invoices):
        """Test: Suspended vendor should trigger escalation"""
        
        invoice = next(
            inv for inv in test_invoices 
            if inv['_test_category'] == 'SUSPENDED_VENDOR'
        )
        
        result = await orchestrator.process_invoice(invoice)
        
        # Should fail B2 and escalate
        assert result['escalated']
        assert 'SUSPENDED' in result['escalation_reasons'][0]
    
    @pytest.mark.asyncio
    async def test_206ab_applicable(self, orchestrator, test_invoices):
        """Test: Section 206AB should trigger higher TDS rate"""
        
        invoice = next(
            inv for inv in test_invoices 
            if inv['_test_category'] == '206AB_APPLICABLE'
        )
        
        result = await orchestrator.process_invoice(invoice)
        
        # Should apply higher TDS rate
        tds_category = result['report'].category_results['D']
        
        # Find TDS rate check
        rate_check = next(
            c for c in tds_category.checks 
            if 'rate' in c.check_name.lower()
        )
        
        # Should flag 206AB
        assert '206AB' in rate_check.reasoning or '206ab' in rate_check.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_famous_edge_case_847(self, orchestrator, test_invoices):
        """Test: The famous INV-2024-0847 composite supply nightmare"""
        
        invoice = next(
            inv for inv in test_invoices 
            if inv['invoice_id'] == 'INV-2024-0847'
        )
        
        result = await orchestrator.process_invoice(invoice)
        
        # This should trigger human review
        assert result['escalated']
        
        # Should have low confidence due to ambiguity
        assert result['report'].average_confidence < 0.80
        
        # Should flag composite vs mixed supply issue
        gst_category = result['report'].category_results['B']
        
        # Look for reasoning about composite supply
        composite_mentioned = any(
            'composite' in check.reasoning.lower() or 'mixed' in check.reasoning.lower()
            for check in gst_category.checks
        )
        
        assert composite_mentioned, "Should identify composite/mixed supply issue"
```

### Phase 3: Accuracy Testing (Week 5-6)

Measure accuracy against expected results.

```python
"""
tests/test_accuracy.py
Measure accuracy on test set
"""

import json
from typing import Dict, List

class AccuracyTester:
    """Test accuracy on complete test set"""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.results = []
    
    async def run_all_tests(self, test_invoices: List[Dict]):
        """Run validation on all test invoices"""
        
        for invoice in test_invoices:
            result = await self.orchestrator.process_invoice(invoice)
            
            self.results.append({
                'invoice_id': invoice['invoice_id'],
                'category': invoice['_test_category'],
                'complexity': invoice['_complexity'],
                'expected': invoice.get('_expected_result'),
                'actual_status': result['report'].overall_status,
                'passed_checks': result['report'].passed_checks,
                'failed_checks': result['report'].failed_checks,
                'confidence': result['report'].average_confidence,
                'escalated': result['escalated']
            })
    
    def calculate_accuracy(self) -> Dict:
        """Calculate accuracy metrics"""
        
        # Overall accuracy
        correct = 0
        total = len(self.results)
        
        for result in self.results:
            expected = result['expected']
            actual = result['actual_status']
            
            # Simplified matching
            if expected == 'PASS' and actual == 'PASS':
                correct += 1
            elif expected == 'FAIL' and actual == 'FAIL':
                correct += 1
            elif expected == 'COMPLEX_ANALYSIS_REQUIRED' and result['escalated']:
                correct += 1
        
        accuracy = correct / total if total > 0 else 0
        
        # By complexity
        by_complexity = {}
        for complexity in ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH', 'EXTREME']:
            complexity_results = [r for r in self.results if r['complexity'] == complexity]
            if complexity_results:
                complexity_correct = sum(1 for r in complexity_results if self._is_correct(r))
                by_complexity[complexity] = complexity_correct / len(complexity_results)
        
        # Edge case handling
        edge_cases = [r for r in self.results if r['complexity'] in ['HIGH', 'VERY_HIGH', 'EXTREME']]
        edge_case_handled = sum(1 for r in edge_cases if r['escalated'] or r['confidence'] > 0.7)
        edge_case_rate = edge_case_handled / len(edge_cases) if edge_cases else 0
        
        return {
            'overall_accuracy': accuracy,
            'total_tests': total,
            'correct': correct,
            'by_complexity': by_complexity,
            'edge_case_handling_rate': edge_case_rate
        }
    
    def _is_correct(self, result: Dict) -> bool:
        """Determine if result is correct"""
        expected = result['expected']
        actual = result['actual_status']
        
        if expected == 'PASS':
            return actual == 'PASS'
        elif expected == 'FAIL':
            return actual == 'FAIL'
        elif expected == 'COMPLEX_ANALYSIS_REQUIRED':
            return result['escalated'] or result['confidence'] < 0.8
        else:
            return False
    
    def generate_report(self) -> str:
        """Generate accuracy report"""
        
        metrics = self.calculate_accuracy()
        
        report = []
        report.append("=" * 80)
        report.append("COMPLIANCE VALIDATOR - ACCURACY REPORT")
        report.append("=" * 80)
        report.append("")
        
        report.append(f"Overall Accuracy: {metrics['overall_accuracy']:.1%}")
        report.append(f"Tests Passed: {metrics['correct']}/{metrics['total_tests']}")
        report.append("")
        
        report.append("Accuracy by Complexity:")
        report.append("-" * 80)
        for complexity, accuracy in sorted(metrics['by_complexity'].items()):
            status = "✓" if accuracy >= 0.75 else "✗"
            report.append(f"{status} {complexity:15s}: {accuracy:.1%}")
        report.append("")
        
        report.append(f"Edge Case Handling: {metrics['edge_case_handling_rate']:.1%}")
        report.append("")
        
        # Benchmarks
        report.append("Benchmark Status:")
        report.append("-" * 80)
        
        if metrics['overall_accuracy'] >= 0.90:
            report.append("✓ EXCELLENT: >90% accuracy achieved")
        elif metrics['overall_accuracy'] >= 0.85:
            report.append("✓ GOOD: >85% accuracy achieved")
        elif metrics['overall_accuracy'] >= 0.75:
            report.append("✓ PASS: >75% accuracy achieved")
        else:
            report.append("✗ NEEDS IMPROVEMENT: <75% accuracy")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)

# Usage
async def run_accuracy_test():
    """Run complete accuracy test"""
    
    # Load test data
    with open('data/test_invoices.json') as f:
        test_invoices = json.load(f)
    
    # Initialize orchestrator
    config = {...}
    orchestrator = OrchestratorAgent(config)
    
    # Run tests
    tester = AccuracyTester(orchestrator)
    await tester.run_all_tests(test_invoices)
    
    # Generate report
    report = tester.generate_report()
    print(report)
    
    # Save results
    with open('accuracy_results.json', 'w') as f:
        json.dump(tester.results, f, indent=2)
```

---

## 🔍 Data Analysis Utilities

### Analyzing Test Data

```python
"""
utils/data_analyzer.py
Utilities for analyzing test data
"""

import json
import pandas as pd
from typing import List, Dict

class TestDataAnalyzer:
    """Analyze test invoice data"""
    
    def __init__(self, test_invoices_path: str):
        with open(test_invoices_path) as f:
            self.invoices = json.load(f)
    
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
    
    def get_by_vendor(self, vendor_gstin: str) -> List[Dict]:
        """Get invoices from specific vendor"""
        return [
            inv for inv in self.invoices 
            if inv['vendor']['gstin'] == vendor_gstin
        ]
    
    def analyze_gst_rates(self) -> pd.DataFrame:
        """Analyze GST rates used in invoices"""
        
        data = []
        for inv in self.invoices:
            for item in inv.get('line_items', []):
                cgst = inv.get('cgst_rate', 0)
                sgst = inv.get('sgst_rate', 0)
                igst = inv.get('igst_rate', 0)
                
                data.append({
                    'invoice_id': inv['invoice_id'],
                    'hsn_sac': item.get('hsn_sac'),
                    'description': item.get('description'),
                    'cgst': cgst,
                    'sgst': sgst,
                    'igst': igst,
                    'total_rate': cgst + sgst + igst
                })
        
        return pd.DataFrame(data)
    
    def analyze_tds_sections(self) -> pd.DataFrame:
        """Analyze TDS sections required"""
        
        # Match vendors to TDS sections
        with open('data/vendor_registry.json') as f:
            vendors = {v['gstin']: v for v in json.load(f)['vendors']}
        
        data = []
        for inv in self.invoices:
            vendor_gstin = inv['vendor']['gstin']
            vendor = vendors.get(vendor_gstin, {})
            
            data.append({
                'invoice_id': inv['invoice_id'],
                'vendor_name': vendor.get('legal_name'),
                'vendor_type': vendor.get('vendor_type'),
                'tds_section': vendor.get('tds_section'),
                'invoice_amount': inv['total_amount']
            })
        
        return pd.DataFrame(data)
    
    def identify_traps(self) -> List[Dict]:
        """Identify known traps in test data"""
        
        traps = []
        
        for inv in self.invoices:
            trap = inv.get('_trap')
            if trap:
                traps.append({
                    'invoice_id': inv['invoice_id'],
                    'category': inv['_test_category'],
                    'trap': trap,
                    'hints': inv.get('_hints', [])
                })
        
        return traps
    
    def generate_summary(self) -> str:
        """Generate test data summary"""
        
        lines = []
        lines.append("=" * 80)
        lines.append("TEST DATA SUMMARY")
        lines.append("=" * 80)
        lines.append("")
        
        # Count by category
        categories = {}
        for inv in self.invoices:
            cat = inv.get('_test_category', 'UNKNOWN')
            categories[cat] = categories.get(cat, 0) + 1
        
        lines.append(f"Total Test Invoices: {len(self.invoices)}")
        lines.append(f"Test Categories: {len(categories)}")
        lines.append("")
        
        # Complexity distribution
        complexity = {}
        for inv in self.invoices:
            comp = inv.get('_complexity', 'UNKNOWN')
            complexity[comp] = complexity.get(comp, 0) + 1
        
        lines.append("Complexity Distribution:")
        for comp, count in sorted(complexity.items()):
            pct = count / len(self.invoices) * 100
            lines.append(f"  {comp:15s}: {count:2d} ({pct:5.1f}%)")
        lines.append("")
        
        # Known traps
        traps = self.identify_traps()
        lines.append(f"Known Traps: {len(traps)}")
        for trap in traps:
            lines.append(f"  - {trap['invoice_id']}: {trap['category']}")
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)

# Usage
analyzer = TestDataAnalyzer('data/test_invoices.json')
print(analyzer.generate_summary())

# Get specific invoices
edge_cases = analyzer.get_by_complexity('EXTREME')
suspended_vendor = analyzer.get_by_category('SUSPENDED_VENDOR')

# Analyze patterns
gst_df = analyzer.analyze_gst_rates()
tds_df = analyzer.analyze_tds_sections()
```

---

## 🎯 Testing Strategy

### Week-by-Week Testing Plan

**Week 1-2: Foundation**
- [ ] Test data model parsing (JSON to Pydantic)
- [ ] Test basic extractor on 2 LOW complexity invoices
- [ ] Test arithmetic validator on all invoices
- [ ] Unit tests for helper functions

**Week 3-4: Core Logic**
- [ ] Test GST validator on 5 MEDIUM complexity invoices
- [ ] Test TDS validator on 3 invoices with different sections
- [ ] Test RAG retrieval (query GST rates, TDS sections)
- [ ] Integration test: full workflow on STANDARD_VALID

**Week 5-6: Edge Cases & Polish**
- [ ] Test all 8 HIGH complexity invoices
- [ ] Test 2 VERY_HIGH complexity invoices
- [ ] Test the EXTREME case (INV-2024-0847)
- [ ] Test escalation logic
- [ ] Full accuracy test on all 21 invoices

### Success Criteria

**Pass (Week 4)**:
- ✓ >75% accuracy on STANDARD cases
- ✓ Basic GST and TDS validation working
- ✓ Graceful error handling

**Good (Week 5)**:
- ✓ >85% accuracy on all cases
- ✓ 50%+ of edge cases handled correctly
- ✓ Escalation working for ambiguous cases

**Excellent (Week 6)**:
- ✓ >90% accuracy on all cases
- ✓ 80%+ of edge cases handled correctly
- ✓ Clear reasoning for all decisions
- ✓ Proper escalation with confidence scoring

---

## 🚨 Critical Test Cases

### Must-Pass Cases (Blockers)

1. **STANDARD_VALID**: Basic validation must work
2. **WRONG_GST_RATE**: Must catch incorrect rates
3. **SUSPENDED_VENDOR**: Must detect inactive GSTINs
4. **HIGH_VALUE_APPROVAL**: Must trigger correct approval level

### Must-Handle Edge Cases

1. **INV-2024-0847**: The famous composite supply case
2. **GTA_RCM**: Forward charge vs RCM determination
3. **206AB_APPLICABLE**: Higher TDS rate application
4. **FY_BOUNDARY**: Temporal validation across financial years

---

## 📊 Sample Test Execution

```bash
# Run unit tests
pytest tests/test_extractor.py -v

# Run integration tests
pytest tests/test_integration.py -v

# Run specific test category
pytest tests/ -k "test_gst" -v

# Run accuracy test
python tests/test_accuracy.py

# Generate coverage report
pytest --cov=agents --cov=validators tests/
```

---

## 🎓 Next Steps

1. **Start with foundation tests** - get basic extraction working
2. **Build incrementally** - add validators one by one
3. **Test continuously** - run tests after each feature
4. **Track accuracy** - measure improvement week over week
5. **Focus on edge cases** - these are the differentiators

**You have 21 real-world test cases. Use them wisely! 🎯**
