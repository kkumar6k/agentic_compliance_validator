# Course Learnings → Project Implementation Mapping

## 🎓 How Your AI Engineering Course Knowledge Applies

---

## 1️⃣ Model Selection Strategy (Week 4)

### Course Learning: Strategic Model Selection

**What you learned**:
- Different models for different tasks
- Cost vs performance tradeoffs
- Benchmarking models (MMLU, HumanEval)
- Matching task complexity to model capability

**How it applies to Compliance Validator**:

| Task | Complexity | Model Choice | Reasoning |
|------|-----------|--------------|-----------|
| Orchestration | Low | GPT-4o-mini | Fast routing decisions, cost-effective |
| Data Extraction | Low-Med | GPT-4o-mini | Structure parsing, field mapping |
| GST Validation | High | Claude-3.5-Sonnet | Complex regulatory reasoning |
| TDS Validation | High | Claude-3.5-Sonnet | Multi-step logical analysis |
| Conflict Resolution | High | Claude-3.5-Sonnet | Superior reasoning, nuanced decisions |
| Report Generation | Low | GPT-4o-mini | Good at structured output |

**Code Example**:
```python
# From your course notes - Model Selection
class ModelSelector:
    def recommend(self, requirements):
        # Match task to model capability
        if requirements["task_type"] == "reasoning":
            return "claude-3.5-sonnet"  # Best for complex logic
        elif requirements["priority"] == "speed":
            return "gpt-4o-mini"  # Fast and cheap
```

**Applied to Project**:
```python
class ValidatorAgent:
    def __init__(self):
        # Use Claude Sonnet for complex reasoning
        self.llm = ChatAnthropic(model="claude-3.5-sonnet")
        
    async def validate_b10_reverse_charge(self, invoice_data):
        # Complex reasoning task - uses Sonnet
        prompt = f"""
        Analyze reverse charge applicability...
        [Complex multi-step reasoning required]
        """
        result = await self.llm.apredict(prompt)
```

---

## 2️⃣ RAG Implementation (Week 5)

### Course Learning: Retrieval Augmented Generation

**What you learned**:
- Vector embeddings and semantic search
- Chunking strategies
- Creating vector stores with Chroma
- Retrieval QA chains
- Multi-query retrieval
- Document loaders and text splitters

**How it applies to Compliance Validator**:

### Pattern 1: Regulation Knowledge RAG

```python
# From your course notes - RAG System
class ProductionRAG:
    def create_vectorstore(self, documents):
        # Split documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        splits = text_splitter.split_documents(documents)
        
        # Create vectorstore
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings
        )
```

**Applied to GST Regulations**:
```python
class GSTRegulationRAG:
    def __init__(self):
        # Embed GST regulations
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # Load GST documents
        loader = DirectoryLoader(
            "data/gst_regulations/",
            glob="**/*.pdf"
        )
        docs = loader.load()
        
        # Chunk strategically (regulations are hierarchical)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " "]  # Preserve context
        )
        chunks = splitter.split_documents(docs)
        
        # Create vector store
        self.vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory="./chroma_db/gst"
        )
    
    async def query_regulation(self, question):
        """Query with context"""
        # Retrieve relevant chunks
        docs = self.vectorstore.similarity_search(question, k=4)
        
        # Build context
        context = "\n\n".join([d.page_content for d in docs])
        
        # Query LLM
        prompt = f"""
        Based on GST regulations:
        {context}
        
        Question: {question}
        
        Provide accurate answer with regulation reference.
        """
        
        answer = await self.llm.apredict(prompt)
        return answer
```

### Pattern 2: Historical Decisions RAG (with Skepticism)

```python
class HistoricalDecisionRAG:
    """
    RAG for past decisions - BUT with built-in skepticism
    15% of historical decisions are INCORRECT
    """
    
    async def find_similar_cases(self, conflict):
        # Retrieve similar cases
        docs = self.vectorstore.similarity_search(query, k=10)
        
        # Analyze for suspicious patterns
        validated_cases = []
        suspicious_cases = []
        
        for doc in docs:
            if self._validate_decision(doc):
                validated_cases.append(doc)
            else:
                suspicious_cases.append(doc)
        
        return {
            'validated': validated_cases,
            'suspicious': suspicious_cases,
            'warning': f"{len(suspicious_cases)} cases flagged as suspicious"
        }
    
    def _validate_decision(self, decision_doc):
        """
        Validate historical decision against regulations
        Don't blindly trust past patterns!
        """
        # Query regulation RAG to verify
        regulation = self.regulation_rag.query(decision_doc.content)
        
        # Check if decision aligns with regulation
        # Use LLM to compare
        prompt = f"""
        Does this historical decision align with regulations?
        
        Decision: {decision_doc.content}
        Regulation: {regulation}
        
        Respond: VALID, SUSPICIOUS, or INVALID
        """
        
        validation = self.llm.predict(prompt)
        return validation == "VALID"
```

### Pattern 3: Multi-Query Retrieval for Complex Cases

```python
# From course notes - Advanced RAG
class AdvancedRAG:
    def multi_query_retrieval(self, question):
        # Generate query variations
        variations = self._generate_variations(question)
        
        # Retrieve for each
        all_docs = []
        for query in variations:
            docs = self.similarity_search(query, k=2)
            all_docs.extend(docs)
        
        # Remove duplicates
        unique_docs = self._deduplicate(all_docs)
        return unique_docs
```

**Applied to Ambiguous Compliance Cases**:
```python
async def resolve_ambiguous_case(self, invoice_data, conflict):
    """
    For complex cases, query from multiple angles
    """
    
    # Generate multiple query perspectives
    queries = [
        f"GST applicability for {invoice_data.service_type}",
        f"Reverse charge rules for {invoice_data.seller_type}",
        f"Interstate vs intrastate for {invoice_data.place_of_supply}"
    ]
    
    # Retrieve from each perspective
    all_context = []
    for query in queries:
        docs = await self.gst_rag.query(query)
        all_context.append(docs)
    
    # Synthesize with LLM
    comprehensive_context = self._merge_contexts(all_context)
    
    # Make informed decision
    decision = await self._reason_with_context(
        invoice_data,
        conflict,
        comprehensive_context
    )
    
    return decision
```

---

## 3️⃣ Prompt Engineering Patterns

### Course Learning: Effective Prompting

**What you learned**:
- Clear and detailed instructions
- Chain-of-thought reasoning
- Few-shot examples
- Structured output (JSON)

**How it applies**:

### Pattern 1: Chain-of-Thought for Complex Validation

```python
async def validate_hsn_match(self, item):
    """B5: HSN code matches product description"""
    
    prompt = f"""
    Validate if product description matches HSN code.
    
    Think step-by-step:
    1. What does HSN code {item.hsn_sac} typically cover?
    2. What product category does "{item.description}" belong to?
    3. Do they align? Consider edge cases.
    4. What is your confidence level?
    
    Product Description: {item.description}
    HSN Code: {item.hsn_sac}
    HSN Definition: {hsn_definition}
    
    Provide your reasoning step-by-step, then conclude:
    {{
        "matches": true/false,
        "confidence": 0-100,
        "reasoning": "step by step analysis",
        "requires_review": true/false
    }}
    """
```

### Pattern 2: Structured Output with JSON

```python
# From course - structured responses
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "compliance_check",
        "schema": {
            "type": "object",
            "properties": {
                "status": {"enum": ["PASS", "FAIL", "WARNING"]},
                "confidence": {"type": "number"},
                "reasoning": {"type": "string"}
            }
        }
    }
}

# Apply to validation
async def validate_check(self, check_data):
    response = await self.llm.predict(
        prompt,
        response_format=response_format
    )
    return json.loads(response)
```

### Pattern 3: Few-Shot Examples for Edge Cases

```python
async def classify_vendor_type(self, vendor_info):
    """Determine TDS section based on vendor type"""
    
    prompt = f"""
    Classify vendor and determine TDS section.
    
    Examples:
    1. Contractor for building work → 194C
    2. Professional consultant → 194J  
    3. Commission agent → 194H
    4. Rent payment to individual → 194I
    
    Now classify:
    Vendor: {vendor_info.name}
    Service: {vendor_info.service_type}
    PAN: {vendor_info.pan}
    
    Section: ?
    """
```

---

## 4️⃣ Agent Architecture Patterns

### Multi-Agent Specialization

**From Course Concept**: Breaking complex tasks into specialized agents

**Applied to Project**:

```
                    Orchestrator
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    Extractor       Validator        Resolver
         │               │               │
         │          ┌────┼────┐         │
         │          ▼    ▼    ▼         │
         │        Cat.A  B  C  D  E     │
         │                               │
         └───────────────┬───────────────┘
                         ▼
                      Reporter
```

**Key Pattern**: Each agent has clear responsibility

```python
# Orchestrator: Workflow coordination
class OrchestratorAgent:
    async def process_invoice(self):
        extraction = await self.extractor.extract()
        validation = await self.validator.validate(extraction)
        resolution = await self.resolver.resolve(validation)
        report = await self.reporter.generate(resolution)
        return report

# Validator: Domain expertise
class ValidatorAgent:
    async def validate(self, extraction):
        results = {}
        for category, validator in self.validators.items():
            results[category] = await validator.validate(extraction.data)
        return self._aggregate(results)

# Resolver: Conflict resolution
class ResolverAgent:
    async def resolve(self, validation):
        conflicts = self._identify_conflicts(validation)
        resolutions = []
        for conflict in conflicts:
            resolution = await self._reason_through_conflict(conflict)
            resolutions.append(resolution)
        return resolutions
```

---

## 5️⃣ Error Handling & Observability

### Course Pattern: Robust Production Systems

```python
# From course - comprehensive error handling
class ProductionRAG:
    def query(self, question):
        try:
            result = self.qa_chain({"query": question})
            return result
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
```

**Applied with Enhanced Observability**:

```python
class ValidatorAgent:
    async def validate_check(self, check_id, data):
        """Validate with full observability"""
        
        start_time = time.time()
        
        try:
            # Execute check
            result = await self._execute_check(check_id, data)
            
            # Log success
            duration = time.time() - start_time
            self.logger.info(
                "Check completed",
                extra={
                    'check_id': check_id,
                    'status': result.status,
                    'confidence': result.confidence,
                    'duration_ms': duration * 1000,
                    'reasoning': result.reasoning
                }
            )
            
            return result
            
        except GSTPortalAPIError as e:
            # Handle API errors gracefully
            self.logger.warning(
                "GST Portal unavailable, using fallback",
                extra={'check_id': check_id, 'error': str(e)}
            )
            return self._fallback_validation(check_id, data)
            
        except Exception as e:
            # Log error with context
            duration = time.time() - start_time
            self.logger.error(
                "Check failed",
                extra={
                    'check_id': check_id,
                    'error': str(e),
                    'duration_ms': duration * 1000
                },
                exc_info=True
            )
            raise
```

---

## 6️⃣ Token Optimization

### Course Learning: Managing Context Windows

**Token-efficient RAG**:
```python
# Chunk strategically
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,      # Small chunks
    chunk_overlap=50     # Minimal overlap
)

# Retrieve only what's needed
docs = vectorstore.similarity_search(query, k=4)  # Not 10 or 20
```

**Applied to Compliance Validator**:

```python
class EfficientValidator:
    """Token-optimized validation"""
    
    async def validate_with_rag(self, check_data):
        """
        Use RAG efficiently:
        1. Small, focused queries
        2. Limited retrieval (k=4)
        3. Summarize context before passing to LLM
        """
        
        # Focused query
        query = self._create_focused_query(check_data)
        
        # Limited retrieval
        docs = await self.rag.query(query, k=4)
        
        # Summarize context to reduce tokens
        context = self._summarize_context(docs, max_length=500)
        
        # Efficient prompt
        prompt = f"""
        Context (summarized): {context}
        Data: {check_data}
        Validate: {check_id}
        """
        
        # Response uses fewer tokens
        result = await self.llm.apredict(prompt)
        return result
```

**Cost Tracking**:
```python
class TokenTracker:
    """Track token usage for cost optimization"""
    
    def track_call(self, agent, tokens_used, model):
        cost = self._calculate_cost(tokens_used, model)
        
        self.usage[agent] += tokens_used
        self.cost[agent] += cost
        
        # Log for monitoring
        logger.info(
            "Token usage",
            agent=agent,
            tokens=tokens_used,
            cost=cost,
            cumulative_cost=self.cost[agent]
        )
```

---

## 🎯 Quick Reference: Course → Project Mapping

| Course Concept | Week | Project Application |
|---------------|------|---------------------|
| Local LLMs (Ollama) | 1 | Could use for development/testing |
| API-based LLMs | 2 | Claude Sonnet for validators |
| Model Selection | 4 | Strategic model per task |
| RAG Basics | 5 | Regulation knowledge base |
| Vector Stores | 5 | Chroma for regulations |
| Document Loaders | 5 | Load GST/TDS docs |
| Text Splitting | 5 | Chunk regulations properly |
| Chain Types | 5 | RetrievalQA for queries |
| Advanced RAG | 5 | Multi-query for conflicts |
| Observability | All | Log agent decisions |

---

## 💡 Key Takeaways

1. **Model Selection Matters**: Don't use Claude Sonnet for everything - be strategic
2. **RAG is Essential**: You can't fit all regulations in context window
3. **Be Skeptical**: Historical decisions have 15% error rate
4. **Multi-Agent Design**: Separation of concerns = cleaner code
5. **Observability First**: Log everything for debugging and auditing
6. **Token Efficiency**: Every token costs money at scale

---

## 🚀 Implementation Priority

Based on course learnings:

**Phase 1 - Foundation** (Weeks 1-2):
- ✅ Set up LLM connections (Week 2 knowledge)
- ✅ Create data models (Python fundamentals)
- ✅ Build basic orchestration (Agent patterns)

**Phase 2 - Core** (Weeks 3-4):
- ✅ Implement RAG systems (Week 5 knowledge)
- ✅ Build validators with model selection (Week 4)
- ✅ Add conflict resolution (Advanced prompting)

**Phase 3 - Polish** (Weeks 5-6):
- ✅ Optimize token usage
- ✅ Add observability
- ✅ Handle edge cases
- ✅ Production hardening

**You have all the knowledge needed from your course. Now it's execution time! 💪**
