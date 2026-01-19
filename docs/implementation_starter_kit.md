# Compliance Validator - Implementation Starter Kit

## 📁 Project Structure

```
compliance_validator/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── extractor.py
│   ├── validator.py
│   ├── resolver.py
│   └── reporter.py
│
├── validators/
│   ├── __init__.py
│   ├── category_a.py  # Document Authenticity
│   ├── category_b.py  # GST Compliance
│   ├── category_c.py  # Arithmetic
│   ├── category_d.py  # TDS Compliance
│   └── category_e.py  # Policy & Business Rules
│
├── rag/
│   ├── __init__.py
│   ├── base_rag.py
│   ├── gst_rag.py
│   ├── tds_rag.py
│   └── historical_rag.py
│
├── tools/
│   ├── __init__.py
│   ├── gst_portal.py
│   ├── tds_calculator.py
│   ├── ocr_engine.py
│   └── pdf_parser.py
│
├── models/
│   ├── __init__.py
│   ├── invoice.py       # Pydantic models
│   ├── validation.py
│   └── reports.py
│
├── utils/
│   ├── __init__.py
│   ├── state_manager.py
│   ├── logger.py
│   └── config.py
│
├── data/
│   ├── invoices/
│   ├── vendor_registry.json
│   ├── gst_rates_schedule.csv
│   ├── hsn_sac_codes.json
│   ├── tds_sections.json
│   ├── company_policy.yaml
│   └── historical_decisions.jsonl
│
├── tests/
│   ├── test_extractor.py
│   ├── test_validator.py
│   └── test_integration.py
│
├── notebooks/
│   ├── 01_exploration.ipynb
│   └── 02_testing.ipynb
│
├── requirements.txt
├── .env.example
├── config.yaml
└── main.py
```

---

## 📦 requirements.txt

```txt
# LLM Providers
openai==1.12.0
anthropic==0.18.0

# LangChain
langchain==0.1.10
langchain-community==0.0.25
langchain-openai==0.0.6
langchain-anthropic==0.1.4

# Vector Store
chromadb==0.4.22
sentence-transformers==2.5.1

# Document Processing
pypdf2==3.0.1
pdfplumber==0.10.3
python-docx==1.1.0
pillow==10.2.0
pytesseract==0.3.10

# Data Processing
pandas==2.2.0
numpy==1.26.4
pydantic==2.6.1
pydantic-settings==2.1.0

# Utilities
python-dotenv==1.0.1
pyyaml==6.0.1
requests==2.31.0
aiohttp==3.9.3

# Monitoring & Logging
structlog==24.1.0

# Testing
pytest==8.0.0
pytest-asyncio==0.23.5
```

---

## 🔧 Configuration Files

### .env.example

```bash
# LLM API Keys
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...

# Model Configuration
ORCHESTRATOR_MODEL=gpt-4o-mini
EXTRACTOR_MODEL=gpt-4o-mini
VALIDATOR_MODEL=claude-3-5-sonnet-20241022
RESOLVER_MODEL=claude-3-5-sonnet-20241022
REPORTER_MODEL=gpt-4o-mini

# RAG Configuration
EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIR=./chroma_db

# Processing Configuration
MAX_CONCURRENT_VALIDATIONS=5
CONFIDENCE_THRESHOLD=0.70
HIGH_VALUE_THRESHOLD=1000000

# External APIs (Mock)
GST_PORTAL_API_URL=http://localhost:8000/mock/gst
GST_PORTAL_API_KEY=mock-key

# Logging
LOG_LEVEL=INFO
LOG_FILE=compliance_validator.log
```

### config.yaml

```yaml
# Validation Configuration
validation:
  categories:
    - id: A
      name: Document Authenticity
      checks: 8
      enabled: true
    - id: B
      name: GST Compliance
      checks: 18
      enabled: true
    - id: C
      name: Arithmetic
      checks: 10
      enabled: true
    - id: D
      name: TDS Compliance
      checks: 12
      enabled: true
    - id: E
      name: Policy & Business Rules
      checks: 10
      enabled: true

# Escalation Rules
escalation:
  low_confidence_threshold: 0.70
  high_value_threshold: 1000000
  first_time_vendor: true
  regulatory_ambiguity: true
  conflict_detected: true

# Agent Configuration
agents:
  orchestrator:
    temperature: 0
    max_retries: 3
  validator:
    temperature: 0.3
    max_tokens: 4000
  resolver:
    temperature: 0.3
    max_tokens: 4000

# RAG Configuration
rag:
  chunk_size: 500
  chunk_overlap: 50
  retrieval_k: 4
  similarity_threshold: 0.7
```

---

## 💻 Core Implementation Files

### models/invoice.py

```python
"""Pydantic models for invoice data"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date
from enum import Enum

class DocumentType(str, Enum):
    TAX_INVOICE = "TAX_INVOICE"
    BILL_OF_SUPPLY = "BILL_OF_SUPPLY"
    CREDIT_NOTE = "CREDIT_NOTE"
    DEBIT_NOTE = "DEBIT_NOTE"

class LineItem(BaseModel):
    """Individual line item in invoice"""
    line_number: int
    description: str
    hsn_sac: str
    quantity: float
    unit: str = "NOS"
    unit_price: float
    amount: float
    discount: float = 0.0
    taxable_value: float
    tax_rate: float
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    
    @validator('amount')
    def validate_amount(cls, v, values):
        """Validate amount calculation"""
        expected = values.get('quantity', 0) * values.get('unit_price', 0)
        if abs(v - expected) > 0.01:
            raise ValueError(f"Amount mismatch: {v} != {expected}")
        return v

class InvoiceData(BaseModel):
    """Complete invoice data structure"""
    
    # Document Information
    invoice_number: str
    invoice_date: date
    document_type: DocumentType = DocumentType.TAX_INVOICE
    
    # Seller Information
    seller_name: str
    seller_gstin: str
    seller_address: str
    seller_state: str
    seller_pan: Optional[str] = None
    
    # Buyer Information
    buyer_name: str
    buyer_gstin: str
    buyer_address: str
    buyer_state: str
    buyer_pan: Optional[str] = None
    
    # Financial Details
    line_items: List[LineItem]
    subtotal: float
    discount: float = 0.0
    taxable_value: float
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    cess: float = 0.0
    total_tax: float
    total_amount: float
    
    # GST Specific
    place_of_supply: str
    irn: Optional[str] = None
    irn_date: Optional[date] = None
    qr_code: Optional[str] = None
    e_invoice_applicable: bool = False
    reverse_charge: bool = False
    
    # TDS Information
    tds_applicable: bool = False
    tds_section: Optional[str] = None
    tds_rate: Optional[float] = None
    tds_amount: Optional[float] = None
    
    # Additional Information
    po_number: Optional[str] = None
    po_date: Optional[date] = None
    payment_terms: Optional[str] = None
    due_date: Optional[date] = None
    
    # Metadata
    extraction_confidence: float
    format_type: str
    raw_data: dict = {}
    
    @validator('total_tax')
    def validate_total_tax(cls, v, values):
        """Validate total tax calculation"""
        expected = values.get('cgst', 0) + values.get('sgst', 0) + \
                   values.get('igst', 0) + values.get('cess', 0)
        if abs(v - expected) > 1.0:  # ₹1 tolerance
            raise ValueError(f"Total tax mismatch: {v} != {expected}")
        return v
    
    @validator('total_amount')
    def validate_total_amount(cls, v, values):
        """Validate total amount calculation"""
        expected = values.get('taxable_value', 0) + values.get('total_tax', 0)
        if abs(v - expected) > 1.0:  # ₹1 tolerance
            raise ValueError(f"Total amount mismatch: {v} != {expected}")
        return v

    def is_interstate(self) -> bool:
        """Check if transaction is interstate"""
        return self.seller_state != self.buyer_state
    
    def is_high_value(self, threshold: float = 1000000) -> bool:
        """Check if invoice exceeds threshold"""
        return self.total_amount > threshold

class ExtractionResult(BaseModel):
    """Result of extraction process"""
    data: InvoiceData
    confidence: float
    format_type: str
    errors: List[str] = []
    warnings: List[str] = []
```

### models/validation.py

```python
"""Validation result models"""

from pydantic import BaseModel
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class CheckResult(BaseModel):
    """Result of a single validation check"""
    check_id: str
    check_name: str
    status: CheckStatus
    confidence: float
    reasoning: str
    severity: Severity = Severity.MEDIUM
    requires_review: bool = False
    rag_context: Optional[List[str]] = None
    timestamp: datetime = datetime.now()

class CategoryResult(BaseModel):
    """Result of category validation"""
    category: str
    category_name: str
    checks: List[CheckResult]
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    average_confidence: float = 0.0
    
    def __init__(self, **data):
        super().__init__(**data)
        self._calculate_stats()
    
    def _calculate_stats(self):
        """Calculate category statistics"""
        self.passed_count = len([c for c in self.checks if c.status == CheckStatus.PASS])
        self.failed_count = len([c for c in self.checks if c.status == CheckStatus.FAIL])
        self.warning_count = len([c for c in self.checks if c.status == CheckStatus.WARNING])
        
        if self.checks:
            self.average_confidence = sum(c.confidence for c in self.checks) / len(self.checks)

class ValidationResult(BaseModel):
    """Complete validation result"""
    invoice_id: str
    timestamp: datetime
    category_results: Dict[str, CategoryResult]
    passed_checks: int = 0
    failed_checks: int = 0
    warnings: int = 0
    average_confidence: float = 0.0
    requires_review: bool = False
    
    def has_conflicts(self) -> bool:
        """Check if validation has conflicts"""
        for category in self.category_results.values():
            for check in category.checks:
                if check.requires_review:
                    return True
        return False
    
    def get_critical_issues(self) -> List[CheckResult]:
        """Get all critical failed checks"""
        issues = []
        for category in self.category_results.values():
            for check in category.checks:
                if check.status == CheckStatus.FAIL and \
                   check.severity in [Severity.HIGH, Severity.CRITICAL]:
                    issues.append(check)
        return issues

class ConflictResolution(BaseModel):
    """Resolution for a specific conflict"""
    conflict_id: str
    interpretation_a: str
    interpretation_b: str
    recommended_interpretation: str
    confidence_score: float
    reasoning: str
    needs_human_review: bool
    risk_level: str
    historical_precedent: Optional[str] = None

class ResolutionResult(BaseModel):
    """Result of conflict resolution"""
    original_validation: ValidationResult
    conflicts: List[Dict]
    resolutions: List[ConflictResolution]
    final_decision: str
    average_confidence: float
    needs_human_review: bool
```

### agents/orchestrator.py

```python
"""Orchestrator Agent - Main workflow coordinator"""

import asyncio
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from utils.state_manager import StateManager
from utils.logger import get_logger
from models.invoice import InvoiceData

logger = get_logger(__name__)

class OrchestratorAgent:
    """
    Orchestrator Agent coordinates the entire validation workflow
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = ChatOpenAI(
            model=config['orchestrator_model'],
            temperature=0
        )
        
        self.state_manager = StateManager()
        
        # Import agents (lazy loading to avoid circular imports)
        from agents.extractor import ExtractorAgent
        from agents.validator import ValidatorAgent
        from agents.resolver import ResolverAgent
        from agents.reporter import ReporterAgent
        
        self.agents = {
            'extractor': ExtractorAgent(config),
            'validator': ValidatorAgent(config),
            'resolver': ResolverAgent(config),
            'reporter': ReporterAgent(config)
        }
        
        logger.info("Orchestrator Agent initialized")
    
    async def process_invoice(self, invoice_path: str) -> Dict[str, Any]:
        """
        Main workflow: Extract → Validate → Resolve → Report
        """
        
        # Create processing state
        state = self.state_manager.create_state(invoice_path)
        logger.info(f"Processing invoice: {invoice_path}", state_id=state.state_id)
        
        try:
            # Step 1: Extract
            logger.info("Starting extraction", state_id=state.state_id)
            extraction_result = await self.agents['extractor'].extract(
                invoice_path, state
            )
            self.state_manager.update_state(
                state.state_id, 
                'extraction', 
                'completed',
                {'confidence': extraction_result.confidence}
            )
            
            # Step 2: Validate
            logger.info("Starting validation", state_id=state.state_id)
            validation_result = await self.agents['validator'].validate(
                extraction_result, state
            )
            self.state_manager.update_state(
                state.state_id,
                'validation',
                'completed',
                {
                    'passed': validation_result.passed_checks,
                    'failed': validation_result.failed_checks
                }
            )
            
            # Step 3: Resolve conflicts (if any)
            if validation_result.has_conflicts():
                logger.info("Conflicts detected, starting resolution", 
                           state_id=state.state_id)
                resolution_result = await self.agents['resolver'].resolve(
                    validation_result, state
                )
                self.state_manager.update_state(
                    state.state_id,
                    'resolution',
                    'completed',
                    {'conflicts_resolved': len(resolution_result.resolutions)}
                )
            else:
                logger.info("No conflicts detected", state_id=state.state_id)
                resolution_result = validation_result
            
            # Step 4: Generate report
            logger.info("Generating report", state_id=state.state_id)
            report = await self.agents['reporter'].generate_report(
                resolution_result, state
            )
            self.state_manager.update_state(
                state.state_id,
                'reporting',
                'completed'
            )
            
            # Step 5: Check escalation
            should_escalate, reasons = self._check_escalation(
                resolution_result,
                extraction_result.data
            )
            
            if should_escalate:
                logger.warning(
                    "Escalation triggered",
                    state_id=state.state_id,
                    reasons=reasons
                )
                await self._escalate(report, resolution_result, reasons)
            
            # Mark complete
            self.state_manager.update_state(
                state.state_id,
                'complete',
                'success'
            )
            
            logger.info("Processing complete", state_id=state.state_id)
            
            return {
                'status': 'success',
                'state_id': state.state_id,
                'report': report,
                'escalated': should_escalate,
                'escalation_reasons': reasons if should_escalate else None
            }
            
        except Exception as e:
            logger.error(
                f"Processing failed: {str(e)}",
                state_id=state.state_id,
                exc_info=True
            )
            await self._handle_error(state, e)
            raise
    
    def _check_escalation(self, resolution_result, invoice_data: InvoiceData):
        """Check if invoice needs escalation"""
        
        reasons = []
        
        # Low confidence
        if resolution_result.average_confidence < self.config['confidence_threshold']:
            reasons.append(
                f"Low confidence: {resolution_result.average_confidence:.1%}"
            )
        
        # High value
        if invoice_data.is_high_value(self.config['high_value_threshold']):
            reasons.append(
                f"High value: ₹{invoice_data.total_amount:,.2f}"
            )
        
        # Critical failures
        critical_issues = resolution_result.get_critical_issues()
        if critical_issues:
            reasons.append(
                f"{len(critical_issues)} critical issues detected"
            )
        
        # Human review requested
        if resolution_result.needs_human_review:
            reasons.append("Human review requested")
        
        return len(reasons) > 0, reasons
    
    async def _escalate(self, report, resolution_result, reasons):
        """Escalate to human reviewer"""
        
        # In production: send to review queue, notify reviewers, etc.
        logger.warning(
            "ESCALATION REQUIRED",
            reasons=reasons,
            invoice_id=resolution_result.invoice_id
        )
        
        # Add escalation metadata to report
        report.add_escalation(reasons)
    
    async def _handle_error(self, state, error):
        """Handle processing errors"""
        
        self.state_manager.update_state(
            state.state_id,
            'error',
            'failed',
            {'error': str(error)}
        )
        
        # In production: send alerts, log to monitoring system
        logger.error(
            "Processing error",
            state_id=state.state_id,
            error=str(error)
        )
```

### agents/extractor.py (Starter)

```python
"""Extractor Agent - Multi-format invoice parsing"""

import json
import csv
from pathlib import Path
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from models.invoice import InvoiceData, ExtractionResult
from utils.logger import get_logger

logger = get_logger(__name__)

class ExtractorAgent:
    """
    Extractor Agent handles multi-format invoice parsing
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = ChatOpenAI(
            model=config['extractor_model'],
            temperature=0
        )
        
        logger.info("Extractor Agent initialized")
    
    async def extract(self, invoice_path: str, state) -> ExtractionResult:
        """Extract data from invoice"""
        
        logger.info(f"Extracting data from: {invoice_path}")
        
        # Detect format
        format_type = self._detect_format(invoice_path)
        logger.info(f"Detected format: {format_type}")
        
        # Route to appropriate extractor
        if format_type == 'json':
            data = await self._extract_json(invoice_path)
        elif format_type == 'csv':
            data = await self._extract_csv(invoice_path)
        elif format_type == 'pdf':
            data = await self._extract_pdf(invoice_path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        # Normalize and validate
        normalized = await self._normalize_data(data)
        
        # Create InvoiceData object
        invoice_data = InvoiceData(**normalized)
        
        # Assess confidence
        confidence = self._assess_extraction_quality(invoice_data)
        
        return ExtractionResult(
            data=invoice_data,
            confidence=confidence,
            format_type=format_type
        )
    
    def _detect_format(self, invoice_path: str) -> str:
        """Detect invoice format"""
        path = Path(invoice_path)
        ext = path.suffix.lower()
        
        if ext == '.json':
            return 'json'
        elif ext == '.csv':
            return 'csv'
        elif ext == '.pdf':
            return 'pdf'
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
    
    async def _extract_json(self, invoice_path: str) -> Dict:
        """Extract from JSON file"""
        with open(invoice_path, 'r') as f:
            data = json.load(f)
        return data
    
    async def _extract_csv(self, invoice_path: str) -> Dict:
        """Extract from CSV file"""
        # Implement CSV parsing logic
        pass
    
    async def _extract_pdf(self, invoice_path: str) -> Dict:
        """Extract from PDF file"""
        # Implement PDF parsing logic
        pass
    
    async def _normalize_data(self, data: Dict) -> Dict:
        """Normalize extracted data to standard format"""
        
        # Implement field mapping and normalization
        # This is where you'd use RAG for field name variations
        
        return data
    
    def _assess_extraction_quality(self, invoice_data: InvoiceData) -> float:
        """Assess quality of extraction"""
        
        # Check for required fields
        score = 1.0
        
        # Deduct for missing optional fields
        if not invoice_data.irn:
            score -= 0.05
        if not invoice_data.po_number:
            score -= 0.05
        
        return max(0.0, score)
```

---

## 🚀 Quick Start Script

### main.py

```python
"""Main entry point for compliance validator"""

import asyncio
from pathlib import Path
from dotenv import load_dotenv
from agents.orchestrator import OrchestratorAgent
from utils.config import load_config
from utils.logger import setup_logging

# Load environment
load_dotenv()

# Setup logging
setup_logging()

# Load configuration
config = load_config()

async def main():
    """Main execution"""
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(config)
    
    # Get invoice path
    invoice_path = "data/invoices/sample_invoice_001.json"
    
    # Process invoice
    result = await orchestrator.process_invoice(invoice_path)
    
    # Display results
    print("\n" + "="*80)
    print("COMPLIANCE VALIDATION RESULT")
    print("="*80)
    print(f"Status: {result['status']}")
    print(f"State ID: {result['state_id']}")
    
    if result['escalated']:
        print(f"\n⚠️  ESCALATION REQUIRED")
        print(f"Reasons:")
        for reason in result['escalation_reasons']:
            print(f"  - {reason}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📝 Development Checklist

### Phase 1: Foundation (Week 1-2)
- [ ] Set up project structure
- [ ] Create virtual environment
- [ ] Install dependencies
- [ ] Define Pydantic models
- [ ] Implement JSON extractor
- [ ] Create basic orchestrator
- [ ] Build arithmetic validator (Category C)
- [ ] Write unit tests

### Phase 2: Core Logic (Week 3-4)
- [ ] Implement GST validator (Category B)
- [ ] Implement TDS validator (Category D)
- [ ] Build RAG systems
- [ ] Add conflict resolver
- [ ] Create report generator
- [ ] Integration testing

### Phase 3: Polish (Week 5-6)
- [ ] Add remaining validators (A, E)
- [ ] Implement PDF extraction
- [ ] Add escalation logic
- [ ] Handle edge cases
- [ ] Performance optimization
- [ ] Documentation

---

## 🧪 Sample Test

```python
"""test_extractor.py"""

import pytest
from agents.extractor import ExtractorAgent

@pytest.fixture
def config():
    return {
        'extractor_model': 'gpt-4o-mini',
        # ... other config
    }

@pytest.fixture
def extractor(config):
    return ExtractorAgent(config)

@pytest.mark.asyncio
async def test_extract_json_invoice(extractor):
    """Test JSON invoice extraction"""
    
    invoice_path = "tests/fixtures/sample_invoice.json"
    state = MockState()
    
    result = await extractor.extract(invoice_path, state)
    
    assert result.confidence > 0.8
    assert result.format_type == 'json'
    assert result.data.invoice_number is not None
    assert result.data.total_amount > 0
```

---

## 📖 Next Steps

1. **Set up environment**:
   ```bash
   # Create project directory
   mkdir compliance_validator
   cd compliance_validator
   
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Copy .env.example to .env and add your API keys
   cp .env.example .env
   ```

2. **Start with Phase 1**:
   - Implement data models
   - Build JSON extractor
   - Create arithmetic validator
   - Test with sample invoices

3. **Iterate and expand**:
   - Add more validators
   - Implement RAG systems
   - Handle edge cases
   - Optimize performance

**Ready to start building! 🚀**
