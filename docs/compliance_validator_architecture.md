# Compliance Validator Agent System Architecture
## Integrating AI Engineering Course Learnings

---

## 🎯 Executive Summary

This document outlines a multi-agent compliance validation system that processes 58-point checks on invoices against Indian GST/TDS regulations. The architecture integrates key learnings from your AI Engineering course:

- **Model Selection Strategy** (Week 4): Strategic use of different models for different tasks
- **RAG Patterns** (Week 5): Knowledge retrieval for regulations and historical decisions
- **Multi-Agent Architecture**: Specialized agents with clear separation of concerns
- **Tool Integration**: External APIs, OCR, and database operations

---

## 📐 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                           │
│  - Workflow coordination                                        │
│  - Agent communication                                          │
│  - Error handling & escalation                                 │
└────────────┬────────────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐      ┌─────────┐
│ EXTRACTOR│◄────►│VALIDATOR│
│  AGENT   │      │  AGENT  │
└─────────┘      └─────────┘
    │                 │
    │                 ▼
    │            ┌─────────┐
    │            │RESOLVER │
    │            │  AGENT  │
    │            └─────────┘
    │                 │
    ▼                 ▼
┌─────────────────────────┐
│    REPORTER AGENT       │
└─────────────────────────┘
         │
         ▼
    ┌─────────┐
    │  OUTPUT │
    │ & AUDIT │
    └─────────┘
```

---

## 🤖 Agent Definitions

### 1. **Orchestrator Agent** 
*Brain of the system - coordinates all agents*

**Model**: GPT-4o-mini or Claude-3.5-Haiku
- **Why**: Fast, cost-effective for coordination tasks
- **Cost**: ~$0.15 per 1M tokens
- **Use Case**: Lightweight decision-making and routing

**Responsibilities**:
- Route invoices to appropriate agents
- Manage workflow state
- Handle errors and retries
- Trigger escalations
- Coordinate agent communication
- Track processing metrics

**Tools**:
- State management database
- Message queue for agent communication
- Logging & monitoring system
- Escalation notification system

**Implementation Pattern**:
```python
class OrchestratorAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.state_db = StateDatabase()
        self.agents = {
            'extractor': ExtractorAgent(),
            'validator': ValidatorAgent(),
            'resolver': ResolverAgent(),
            'reporter': ReporterAgent()
        }
        
    async def process_invoice(self, invoice_path):
        """Main workflow orchestration"""
        # Create processing state
        state = self.state_db.create_state(invoice_path)
        
        try:
            # Step 1: Extract data
            extraction_result = await self.agents['extractor'].extract(
                invoice_path, state
            )
            
            # Step 2: Validate
            validation_result = await self.agents['validator'].validate(
                extraction_result, state
            )
            
            # Step 3: Resolve conflicts if any
            if validation_result.has_conflicts():
                resolution = await self.agents['resolver'].resolve(
                    validation_result, state
                )
            else:
                resolution = validation_result
            
            # Step 4: Generate report
            report = await self.agents['reporter'].generate_report(
                resolution, state
            )
            
            # Step 5: Check escalation needs
            if self._needs_escalation(resolution):
                await self._escalate(report, resolution)
            
            return report
            
        except Exception as e:
            await self._handle_error(state, e)
            raise
```

---

### 2. **Extractor Agent**
*Handles multi-format invoice parsing*

**Model Strategy** (Multiple models for different formats):
- **PDFs with text**: PyPDF2 + GPT-4o-mini for structure
- **Scanned images**: Azure Document Intelligence + Claude-3.5-Sonnet for complex layouts
- **JSON/CSV**: Direct parsing + validation

**Responsibilities**:
- Parse invoices from PDF, images, JSON, CSV
- OCR for scanned documents
- Data normalization and cleaning
- Handle OCR errors (O vs 0, I vs 1)
- Extract structured data
- Initial data quality checks

**Tools**:
- PyPDF2 / pdfplumber for PDF text extraction
- Azure Document Intelligence / Tesseract for OCR
- OpenCV for image preprocessing
- JSON/CSV parsers
- Data validation schemas (Pydantic)

**RAG Integration**:
```python
class ExtractorAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini")
        self.ocr_model = ChatAnthropic(model="claude-3.5-sonnet")  # Better vision
        self.rag = InvoiceFieldRAG()  # RAG for field mappings
        
    async def extract(self, invoice_path, state):
        """Extract data from invoice"""
        
        # Detect format
        format_type = self._detect_format(invoice_path)
        
        # Route to appropriate extractor
        if format_type == 'pdf_text':
            data = await self._extract_pdf_text(invoice_path)
        elif format_type == 'pdf_image':
            data = await self._extract_pdf_image(invoice_path)
        elif format_type == 'image':
            data = await self._extract_image(invoice_path)
        elif format_type == 'json':
            data = self._extract_json(invoice_path)
        elif format_type == 'csv':
            data = self._extract_csv(invoice_path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        # Normalize and clean
        normalized = await self._normalize_data(data)
        
        # Validate extraction quality
        quality_score = self._assess_extraction_quality(normalized)
        
        return ExtractionResult(
            data=normalized,
            confidence=quality_score,
            format_type=format_type,
            raw_data=data
        )
    
    async def _normalize_data(self, data):
        """Use RAG to handle field variations"""
        # Query RAG for field mappings
        field_mappings = await self.rag.get_field_mappings(data.keys())
        
        # Normalize field names
        normalized = {}
        for key, value in data.items():
            standard_key = field_mappings.get(key, key)
            normalized[standard_key] = value
        
        # Clean common OCR errors
        normalized = self._clean_ocr_errors(normalized)
        
        return normalized
```

**Data Structure**:
```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class InvoiceData(BaseModel):
    """Standardized invoice data structure"""
    
    # Document Info
    invoice_number: str
    invoice_date: date
    document_type: str = "TAX_INVOICE"
    
    # Seller Info
    seller_name: str
    seller_gstin: str
    seller_address: str
    seller_state: str
    
    # Buyer Info
    buyer_name: str
    buyer_gstin: str
    buyer_address: str
    buyer_state: str
    
    # Financial
    line_items: List[LineItem]
    subtotal: float
    discount: float = 0.0
    taxable_value: float
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    total_tax: float
    total_amount: float
    
    # GST Specific
    place_of_supply: str
    hsn_sac_codes: List[str]
    irn: Optional[str] = None
    qr_code: Optional[str] = None
    
    # TDS
    tds_section: Optional[str] = None
    tds_amount: Optional[float] = None
    tds_rate: Optional[float] = None
    
    # Metadata
    extraction_confidence: float
    raw_data: dict

class LineItem(BaseModel):
    description: str
    hsn_sac: str
    quantity: float
    unit_price: float
    amount: float
    tax_rate: float
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
```

---

### 3. **Validator Agent**
*Executes 58-point compliance checks*

**Model**: Claude-3.5-Sonnet
- **Why**: Best reasoning capabilities for complex compliance logic
- **Cost**: ~$3.00 per 1M tokens
- **Use Case**: Complex regulatory validation requiring deep reasoning

**Architecture**:
```
ValidatorAgent
├── CategoryA_Agent (Document Authenticity)
├── CategoryB_Agent (GST Compliance)  
├── CategoryC_Agent (Arithmetic)
├── CategoryD_Agent (TDS Compliance)
└── CategoryE_Agent (Policy & Business Rules)
```

**RAG Integration**:
```python
class ValidatorAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-3.5-sonnet")
        
        # RAG systems for different knowledge domains
        self.gst_rag = ComplianceRAG(domain="gst_regulations")
        self.tds_rag = ComplianceRAG(domain="tds_regulations")
        self.policy_rag = ComplianceRAG(domain="company_policy")
        
        # Reference data
        self.vendor_registry = VendorRegistry()
        self.gst_rates = GSTRateSchedule()
        self.hsn_sac_codes = HSNSACMaster()
        self.tds_sections = TDSSectionRules()
        
        # Specialized validators
        self.validators = {
            'A': DocumentAuthenticityValidator(self.llm, self.vendor_registry),
            'B': GSTComplianceValidator(self.llm, self.gst_rag),
            'C': ArithmeticValidator(self.llm),
            'D': TDSComplianceValidator(self.llm, self.tds_rag),
            'E': PolicyValidator(self.llm, self.policy_rag)
        }
    
    async def validate(self, extraction_result, state):
        """Run all validation checks"""
        
        validation_results = {}
        
        # Run category validators in parallel
        tasks = []
        for category, validator in self.validators.items():
            task = validator.validate(extraction_result.data, state)
            tasks.append((category, task))
        
        # Collect results
        for category, task in tasks:
            results = await task
            validation_results[category] = results
        
        # Aggregate results
        overall_result = self._aggregate_results(validation_results)
        
        return ValidationResult(
            category_results=validation_results,
            passed_checks=overall_result['passed'],
            failed_checks=overall_result['failed'],
            warnings=overall_result['warnings'],
            confidence_scores=overall_result['confidences']
        )
```

**Category B: GST Compliance Validator** (Example):
```python
class GSTComplianceValidator:
    def __init__(self, llm, gst_rag):
        self.llm = llm
        self.gst_rag = gst_rag
        self.gst_portal = GSTPortalMock()  # Mock API
    
    async def validate(self, invoice_data, state):
        """Execute 18 GST compliance checks"""
        
        checks = []
        
        # B1: GSTIN format validation
        checks.append(await self._check_b1_gstin_format(invoice_data))
        
        # B2: GSTIN active status (requires API call)
        checks.append(await self._check_b2_gstin_active(invoice_data))
        
        # B3: State code match
        checks.append(await self._check_b3_state_code(invoice_data))
        
        # B4-B18: Additional checks...
        # ... (implement all 18 checks)
        
        return CategoryResult(category='B', checks=checks)
    
    async def _check_b5_hsn_matches_description(self, invoice_data):
        """B5: HSN code matches product description (High complexity)"""
        
        # Use RAG to retrieve HSN code mappings
        for item in invoice_data.line_items:
            # Query RAG for HSN code information
            hsn_info = await self.gst_rag.query(
                f"What products are covered by HSN code {item.hsn_sac}?"
            )
            
            # Use LLM to reason about match
            prompt = f"""
            Determine if the product description matches the HSN code.
            
            HSN Code: {item.hsn_sac}
            HSN Definition: {hsn_info}
            Product Description: {item.description}
            
            Does the description match the HSN code? Provide:
            1. Match status (Yes/No/Uncertain)
            2. Confidence score (0-100)
            3. Reasoning
            
            Respond in JSON format.
            """
            
            response = await self.llm.apredict(prompt)
            result = json.loads(response)
            
            if result['match_status'] == 'No':
                return CheckResult(
                    check_id='B5',
                    status='FAIL',
                    confidence=result['confidence'] / 100,
                    reasoning=result['reasoning'],
                    severity='HIGH'
                )
            elif result['match_status'] == 'Uncertain':
                return CheckResult(
                    check_id='B5',
                    status='WARNING',
                    confidence=result['confidence'] / 100,
                    reasoning=result['reasoning'],
                    severity='MEDIUM',
                    requires_review=True
                )
        
        return CheckResult(
            check_id='B5',
            status='PASS',
            confidence=0.95,
            reasoning='All HSN codes match product descriptions'
        )
    
    async def _check_b10_reverse_charge(self, invoice_data):
        """B10: Reverse charge mechanism applicability (High complexity)"""
        
        # Query RAG for reverse charge rules
        query = f"""
        Vendor type: {invoice_data.seller_type}
        Service category: {invoice_data.service_category}
        
        Is reverse charge mechanism applicable?
        """
        
        rag_result = await self.gst_rag.query_with_confidence(query)
        
        # Use LLM for complex reasoning
        prompt = f"""
        Determine if reverse charge mechanism is applicable.
        
        Invoice Details:
        - Seller GSTIN: {invoice_data.seller_gstin}
        - Buyer GSTIN: {invoice_data.buyer_gstin}
        - Service: {invoice_data.line_items[0].description}
        - Amount: {invoice_data.total_amount}
        
        Regulatory Context:
        {rag_result['context']}
        
        Analyze and determine:
        1. Is reverse charge applicable?
        2. What is the confidence level?
        3. What is the reasoning?
        4. Are there any ambiguities?
        
        Respond in JSON.
        """
        
        response = await self.llm.apredict(prompt)
        result = json.loads(response)
        
        # Flag for review if confidence is low
        requires_review = result['confidence'] < 70 or result.get('ambiguities')
        
        return CheckResult(
            check_id='B10',
            status='PASS' if not result['applicable'] else 'FAIL',
            confidence=result['confidence'] / 100,
            reasoning=result['reasoning'],
            requires_review=requires_review,
            severity='HIGH',
            rag_context=rag_result['sources']
        )
```

**Temporal Validity Handling**:
```python
class TemporalValidator:
    """Handles time-based regulation changes"""
    
    def __init__(self):
        self.regulation_history = RegulationHistoryRAG()
    
    async def get_applicable_rules(self, invoice_date, rule_type):
        """Get regulations applicable on invoice date"""
        
        query = f"""
        What were the {rule_type} rules applicable on {invoice_date}?
        Include any transitional provisions.
        """
        
        rules = await self.regulation_history.query(query)
        
        return rules
    
    def handle_transition_period(self, invoice_date, rule_change_date):
        """Handle invoices in transition periods"""
        
        # Check if invoice is in transition period
        # (e.g., March-April GST year boundary)
        
        if self._is_in_transition(invoice_date, rule_change_date):
            return {
                'status': 'TRANSITION',
                'applicable_rules': 'BOTH',
                'guidance': 'Apply most favorable interpretation'
            }
        
        return None
```

---

### 4. **Resolver Agent**
*Handles conflicts and ambiguities*

**Model**: Claude-3.5-Sonnet
- **Why**: Superior reasoning for conflict resolution
- **Pattern**: Chain-of-Thought reasoning

**Responsibilities**:
- Identify conflicting validation results
- Reason through multiple interpretations
- Make recommendations with confidence scores
- Flag for human review when needed
- Document decision reasoning

**Implementation**:
```python
class ResolverAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-3.5-sonnet", temperature=0.3)
        self.decision_rag = HistoricalDecisionRAG()
        self.threshold_confidence = 0.70
    
    async def resolve(self, validation_result, state):
        """Resolve conflicts and ambiguities"""
        
        conflicts = self._identify_conflicts(validation_result)
        
        resolutions = []
        for conflict in conflicts:
            resolution = await self._resolve_conflict(conflict, validation_result)
            resolutions.append(resolution)
        
        return ResolutionResult(
            original_validation=validation_result,
            conflicts=conflicts,
            resolutions=resolutions,
            final_decision=self._make_final_decision(resolutions)
        )
    
    async def _resolve_conflict(self, conflict, validation_result):
        """Resolve a specific conflict"""
        
        # Check historical decisions (but be skeptical!)
        similar_cases = await self.decision_rag.find_similar_cases(conflict)
        
        # Analyze historical decisions for consistency
        historical_analysis = await self._analyze_historical_decisions(similar_cases)
        
        # Use LLM for reasoning
        prompt = f"""
        CONFLICT RESOLUTION TASK
        
        Conflict:
        {json.dumps(conflict, indent=2)}
        
        Current Validation Result:
        {json.dumps(validation_result.to_dict(), indent=2)}
        
        Historical Similar Cases:
        {json.dumps(similar_cases, indent=2)}
        
        Historical Decision Analysis:
        {historical_analysis}
        
        Your task:
        1. Analyze both interpretations of the regulation
        2. Consider precedent but validate against regulations
        3. Make a recommendation with confidence score
        4. Identify if this needs human review
        5. Document your reasoning clearly
        
        Respond in JSON format with:
        - interpretation_a: first interpretation
        - interpretation_b: second interpretation
        - recommended_interpretation: which one to use
        - confidence_score: 0-100
        - reasoning: step-by-step logic
        - needs_human_review: boolean
        - risk_level: LOW/MEDIUM/HIGH
        """
        
        response = await self.llm.apredict(prompt)
        resolution = json.loads(response)
        
        # Apply confidence threshold
        if resolution['confidence_score'] < self.threshold_confidence * 100:
            resolution['needs_human_review'] = True
            resolution['escalation_reason'] = 'Low confidence'
        
        return ConflictResolution(**resolution)
    
    async def _analyze_historical_decisions(self, similar_cases):
        """Analyze historical decisions but detect incorrect ones"""
        
        # Use LLM to identify suspicious patterns
        prompt = f"""
        Analyze these historical decisions for consistency and correctness.
        
        Cases:
        {json.dumps(similar_cases, indent=2)}
        
        Identify:
        1. Are decisions consistent across cases?
        2. Do any decisions seem suspicious or incorrect?
        3. What is the dominant pattern?
        4. What is the confidence in this pattern?
        
        Remember: 15% of historical decisions are INCORRECT.
        Be skeptical and validate against regulations.
        """
        
        analysis = await self.llm.apredict(prompt)
        
        return analysis
```

**Escalation Logic**:
```python
class EscalationManager:
    """Manages escalation to human reviewers"""
    
    def __init__(self):
        self.escalation_rules = {
            'low_confidence': 0.70,
            'high_value_threshold': 1000000,  # 10 lakhs
            'first_time_vendor': True,
            'regulatory_ambiguity': True,
            'conflict_detected': True
        }
    
    def should_escalate(self, resolution_result, invoice_data):
        """Determine if invoice needs human review"""
        
        reasons = []
        
        # Check confidence
        if resolution_result.average_confidence < self.escalation_rules['low_confidence']:
            reasons.append('Low confidence decision')
        
        # Check invoice value
        if invoice_data.total_amount > self.escalation_rules['high_value_threshold']:
            reasons.append(f'High value invoice: ₹{invoice_data.total_amount:,.2f}')
        
        # Check vendor status
        if invoice_data.is_first_time_vendor:
            reasons.append('First-time vendor')
        
        # Check for ambiguities
        if resolution_result.has_regulatory_ambiguity:
            reasons.append('Regulatory ambiguity detected')
        
        # Check for conflicts
        if len(resolution_result.conflicts) > 0:
            reasons.append(f'{len(resolution_result.conflicts)} conflicts detected')
        
        if reasons:
            return True, reasons
        
        return False, []
```

---

### 5. **Reporter Agent**
*Generates actionable reports*

**Model**: GPT-4o-mini
- **Why**: Good at structured output generation, cost-effective
- **Use Case**: Report formatting and summarization

**Responsibilities**:
- Generate compliance reports
- Create executive summaries
- Format for different audiences
- Include audit trails
- Generate visualizations

**Implementation**:
```python
class ReporterAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini")
        self.template_engine = ReportTemplateEngine()
    
    async def generate_report(self, resolution_result, state):
        """Generate comprehensive compliance report"""
        
        # Create report sections
        executive_summary = await self._generate_executive_summary(resolution_result)
        detailed_findings = self._format_detailed_findings(resolution_result)
        recommendations = await self._generate_recommendations(resolution_result)
        audit_trail = self._create_audit_trail(state)
        
        # Compile report
        report = ComplianceReport(
            invoice_id=state.invoice_id,
            timestamp=datetime.now(),
            executive_summary=executive_summary,
            overall_status=self._determine_status(resolution_result),
            passed_checks=resolution_result.passed_count,
            failed_checks=resolution_result.failed_count,
            warnings=resolution_result.warning_count,
            detailed_findings=detailed_findings,
            recommendations=recommendations,
            confidence_score=resolution_result.average_confidence,
            requires_review=resolution_result.needs_human_review,
            audit_trail=audit_trail
        )
        
        # Generate different formats
        json_report = report.to_json()
        pdf_report = await self._generate_pdf(report)
        excel_report = self._generate_excel(report)
        
        return ReportPackage(
            json=json_report,
            pdf=pdf_report,
            excel=excel_report
        )
    
    async def _generate_executive_summary(self, resolution_result):
        """Generate executive summary using LLM"""
        
        prompt = f"""
        Create an executive summary of this compliance validation.
        
        Results:
        - Total Checks: 58
        - Passed: {resolution_result.passed_count}
        - Failed: {resolution_result.failed_count}
        - Warnings: {resolution_result.warning_count}
        - Confidence: {resolution_result.average_confidence:.1%}
        
        Key Issues:
        {json.dumps(resolution_result.get_critical_issues(), indent=2)}
        
        Write a 3-paragraph executive summary:
        1. Overall assessment
        2. Critical issues (if any)
        3. Recommendation
        
        Keep it business-focused and actionable.
        """
        
        summary = await self.llm.apredict(prompt)
        return summary
```

---

## 🗄️ RAG System Design

### Knowledge Domains

```python
class ComplianceRAG:
    """Base RAG system for compliance knowledge"""
    
    def __init__(self, domain):
        self.domain = domain
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.vectorstore = self._initialize_vectorstore()
        self.llm = ChatOpenAI(model="gpt-4o-mini")
    
    def _initialize_vectorstore(self):
        """Initialize domain-specific vector store"""
        
        if self.domain == "gst_regulations":
            docs = self._load_gst_regulations()
        elif self.domain == "tds_regulations":
            docs = self._load_tds_regulations()
        elif self.domain == "company_policy":
            docs = self._load_company_policy()
        elif self.domain == "historical_decisions":
            docs = self._load_historical_decisions()
        else:
            raise ValueError(f"Unknown domain: {self.domain}")
        
        # Process documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        splits = text_splitter.split_documents(docs)
        
        # Create vectorstore
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            persist_directory=f"./chroma_db/{self.domain}"
        )
        
        return vectorstore
    
    async def query(self, question, k=4):
        """Query the RAG system"""
        
        # Retrieve relevant documents
        docs = self.vectorstore.similarity_search(question, k=k)
        
        # Create context
        context = "\n\n".join([doc.page_content for doc in docs])
        
        # Query LLM
        prompt = f"""
        Based on the following context, answer the question.
        
        Context:
        {context}
        
        Question: {question}
        
        Answer:
        """
        
        answer = await self.llm.apredict(prompt)
        
        return {
            'answer': answer,
            'context': context,
            'sources': docs
        }
    
    async def query_with_confidence(self, question):
        """Query with confidence scoring"""
        
        result = await self.query(question)
        
        # Score confidence based on source relevance
        confidence = self._calculate_confidence(question, result['sources'])
        
        result['confidence'] = confidence
        return result
```

### Historical Decision RAG (with Skepticism)

```python
class HistoricalDecisionRAG(ComplianceRAG):
    """RAG for historical decisions - with built-in skepticism"""
    
    def __init__(self):
        super().__init__(domain="historical_decisions")
        self.suspicious_pattern_detector = SuspiciousPatternDetector()
    
    def _load_historical_decisions(self):
        """Load and annotate historical decisions"""
        
        # Load from historical_decisions.jsonl
        decisions = []
        with open("data/historical_decisions.jsonl") as f:
            for line in f:
                decision = json.loads(line)
                decisions.append(decision)
        
        # Convert to documents
        docs = []
        for decision in decisions:
            doc = Document(
                page_content=self._format_decision(decision),
                metadata={
                    'invoice_id': decision['invoice_id'],
                    'date': decision['date'],
                    'decision': decision['decision'],
                    'validator': decision['validator']
                }
            )
            docs.append(doc)
        
        return docs
    
    async def find_similar_cases(self, conflict):
        """Find similar historical cases"""
        
        query = self._format_conflict_as_query(conflict)
        
        # Retrieve similar cases
        docs = self.vectorstore.similarity_search(query, k=10)
        
        # Filter for suspicious patterns
        filtered_docs = []
        for doc in docs:
            if not self.suspicious_pattern_detector.is_suspicious(doc):
                filtered_docs.append(doc)
        
        # If too many were filtered, include with warning
        if len(filtered_docs) < 3:
            filtered_docs = docs[:5]
            warning = "Limited high-quality precedents available"
        else:
            warning = None
        
        return {
            'cases': filtered_docs,
            'warning': warning
        }

class SuspiciousPatternDetector:
    """Detects potentially incorrect historical decisions"""
    
    def __init__(self):
        self.red_flags = [
            'missing_justification',
            'contradicts_regulation',
            'inconsistent_with_peers',
            'unusual_interpretation'
        ]
    
    def is_suspicious(self, decision_doc):
        """Check if decision shows red flags"""
        
        # Analyze decision content
        content = decision_doc.page_content
        metadata = decision_doc.metadata
        
        # Check for red flags
        flags = []
        
        # Missing justification
        if 'reasoning' not in content or len(content) < 100:
            flags.append('missing_justification')
        
        # Check consistency (simplified)
        # In production, compare with regulation text
        
        return len(flags) > 0
```

---

## 🛠️ Tool Integration

### GST Portal Mock API

```python
class GSTPortalMock:
    """Mock GST Portal API for GSTIN validation"""
    
    def __init__(self):
        self.delay_range = (0.5, 2.0)  # Simulate API latency
    
    async def verify_gstin(self, gstin):
        """Verify GSTIN status"""
        
        # Simulate API call delay
        await asyncio.sleep(random.uniform(*self.delay_range))
        
        # Validation logic
        if not self._validate_format(gstin):
            return {
                'status': 'INVALID',
                'error': 'Invalid GSTIN format',
                'gstin': gstin
            }
        
        # Simulate realistic responses
        scenarios = [
            ('ACTIVE', 0.70),
            ('CANCELLED', 0.10),
            ('SUSPENDED', 0.05),
            ('API_ERROR', 0.10),
            ('RATE_LIMIT', 0.05)
        ]
        
        status = random.choices(
            [s[0] for s in scenarios],
            weights=[s[1] for s in scenarios]
        )[0]
        
        if status == 'API_ERROR':
            raise GSTPortalAPIError("Unable to connect to GST portal")
        
        if status == 'RATE_LIMIT':
            raise GSTPortalRateLimitError("Rate limit exceeded. Try after 60 seconds")
        
        return {
            'status': status,
            'gstin': gstin,
            'trade_name': self._generate_trade_name(),
            'state': gstin[0:2],
            'registration_date': '2018-07-01'
        }
```

### TDS Calculator Tool

```python
class TDSCalculator:
    """Calculate TDS based on regulations"""
    
    def __init__(self):
        self.tds_rag = ComplianceRAG(domain="tds_regulations")
        self.sections = self._load_tds_sections()
    
    async def calculate_tds(self, invoice_data, vendor_info):
        """Calculate TDS amount and section"""
        
        # Determine applicable section
        section = await self._determine_section(invoice_data, vendor_info)
        
        # Get TDS rate
        rate = self._get_tds_rate(section, vendor_info)
        
        # Calculate TDS amount
        tds_base = self._calculate_tds_base(invoice_data)
        tds_amount = tds_base * (rate / 100)
        
        return TDSCalculation(
            section=section,
            rate=rate,
            base_amount=tds_base,
            tds_amount=tds_amount,
            reasoning=self._explain_calculation(section, rate, tds_base)
        )
    
    async def _determine_section(self, invoice_data, vendor_info):
        """Determine TDS section (194C/194J/etc.)"""
        
        query = f"""
        Determine TDS section for:
        - Service type: {invoice_data.service_type}
        - Vendor type: {vendor_info.vendor_type}
        - Amount: {invoice_data.total_amount}
        """
        
        result = await self.tds_rag.query(query)
        
        # Parse section from result
        section = self._extract_section(result['answer'])
        
        return section
```

---

## 📊 State Management & Monitoring

### State Database

```python
class StateDatabase:
    """Track processing state for each invoice"""
    
    def __init__(self):
        self.db = {}  # In production: use Redis/PostgreSQL
    
    def create_state(self, invoice_path):
        """Create processing state"""
        
        state_id = str(uuid.uuid4())
        state = ProcessingState(
            state_id=state_id,
            invoice_path=invoice_path,
            status='CREATED',
            created_at=datetime.now(),
            steps=[]
        )
        
        self.db[state_id] = state
        return state
    
    def update_state(self, state_id, step_name, status, data=None):
        """Update processing step"""
        
        state = self.db[state_id]
        state.steps.append(Step(
            name=step_name,
            status=status,
            timestamp=datetime.now(),
            data=data
        ))
        state.status = status
        state.updated_at = datetime.now()
    
    def get_state(self, state_id):
        """Retrieve state"""
        return self.db.get(state_id)

class ProcessingState:
    def __init__(self, state_id, invoice_path, status, created_at, steps):
        self.state_id = state_id
        self.invoice_path = invoice_path
        self.status = status
        self.created_at = created_at
        self.updated_at = created_at
        self.steps = steps
        self.metrics = {}
```

### Observability System

```python
class ObservabilitySystem:
    """Comprehensive logging and monitoring"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics_collector = MetricsCollector()
    
    def log_agent_reasoning(self, agent_name, input_data, output_data, reasoning):
        """Log agent decision-making"""
        
        self.logger.info(
            "Agent Decision",
            extra={
                'agent': agent_name,
                'input': input_data,
                'output': output_data,
                'reasoning': reasoning,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def log_tool_call(self, tool_name, params, result, duration):
        """Log tool invocations"""
        
        self.logger.info(
            "Tool Call",
            extra={
                'tool': tool_name,
                'params': params,
                'result': result,
                'duration_ms': duration * 1000,
                'timestamp': datetime.now().isoformat()
            }
        )
        
        # Collect metrics
        self.metrics_collector.record_tool_call(tool_name, duration)
    
    def log_confidence_score(self, check_id, score, reasoning):
        """Log confidence scores"""
        
        self.logger.info(
            "Confidence Score",
            extra={
                'check_id': check_id,
                'score': score,
                'reasoning': reasoning
            }
        )
```

---

## 🎯 Implementation Strategy

### Phase 1: Foundation (Week 1-2)

**Priority Tasks**:
1. Set up development environment
2. Implement data models (Pydantic schemas)
3. Build Extractor Agent for JSON/CSV
4. Create basic Category C validator (Arithmetic)
5. Set up state management
6. Implement basic orchestration

**Deliverables**:
- [ ] Working invoice parser for structured data
- [ ] Basic arithmetic validation (10 checks)
- [ ] Simple orchestration flow
- [ ] Unit tests for core components

### Phase 2: Core Logic (Week 3-4)

**Priority Tasks**:
1. Implement GST Compliance Agent (Category B)
2. Implement TDS Compliance Agent (Category D)
3. Build RAG systems for regulations
4. Add conflict resolution logic
5. Implement reporter agent

**Deliverables**:
- [ ] GST validation (18 checks)
- [ ] TDS validation (12 checks)
- [ ] RAG-powered knowledge retrieval
- [ ] Basic conflict resolution
- [ ] Report generation

### Phase 3: Polish (Week 5-6)

**Priority Tasks**:
1. Add Document Authenticity checks (Category A)
2. Add Policy validation (Category E)
3. Implement PDF/Image extraction
4. Add escalation logic
5. Handle edge cases
6. Performance optimization

**Deliverables**:
- [ ] Complete 58-point validation
- [ ] Multi-format invoice support
- [ ] Escalation workflows
- [ ] Edge case handling
- [ ] Production-ready system

---

## 🧪 Testing Strategy

```python
class ValidationTestSuite:
    """Comprehensive testing for compliance validator"""
    
    def test_standard_cases(self):
        """Test on standard invoices (75% accuracy target)"""
        pass
    
    def test_edge_cases(self):
        """Test on edge cases (50% handling target)"""
        pass
    
    def test_ocr_errors(self):
        """Test handling of OCR errors"""
        pass
    
    def test_temporal_validity(self):
        """Test historical regulation application"""
        pass
    
    def test_escalation_logic(self):
        """Test human-in-the-loop triggers"""
        pass
    
    def test_historical_trap(self):
        """Verify we don't replicate incorrect decisions"""
        pass
```

---

## 💰 Cost Estimation

### Per Invoice Processing Cost:

| Component | Model | Tokens | Cost |
|-----------|-------|--------|------|
| Orchestrator | GPT-4o-mini | 1,000 | $0.00015 |
| Extractor | GPT-4o-mini | 3,000 | $0.00045 |
| Validator | Claude-3.5-Sonnet | 8,000 | $0.024 |
| Resolver | Claude-3.5-Sonnet | 4,000 | $0.012 |
| Reporter | GPT-4o-mini | 2,000 | $0.0003 |
| RAG Queries | GPT-4o-mini | 5,000 | $0.00075 |
| **Total** | | **23,000** | **~$0.038** |

**At scale** (1000 invoices/month): ~$38/month

---

## 🚀 Key Success Factors

1. **Strategic Model Selection**:
   - Use lightweight models for routing/formatting
   - Reserve Claude Sonnet for complex reasoning
   - Leverage RAG to reduce token usage

2. **RAG Implementation**:
   - Separate knowledge domains
   - Maintain regulation history
   - Be skeptical of historical decisions

3. **Error Handling**:
   - Graceful degradation on API failures
   - Confidence scoring on all decisions
   - Clear escalation paths

4. **Observability**:
   - Log all agent reasoning
   - Track confidence scores
   - Monitor processing time
   - Audit trail for every decision

5. **Human-in-the-Loop**:
   - Clear escalation criteria
   - Actionable reports
   - Learning from corrections

---

## 📚 Next Steps

1. Review this architecture
2. Set up development environment
3. Implement Phase 1 foundation
4. Test with sample invoices
5. Iterate based on results

This architecture integrates your AI Engineering course learnings with enterprise-grade compliance validation. Ready to start building! 🚀
