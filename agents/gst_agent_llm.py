"""
GST Agent - LLM-Powered Validator with RAG
Uses LangChain + RAG to validate GST compliance
"""

from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from utils.llm_factory import get_llm, GROK_BETA
from langchain_core.messages import HumanMessage, AIMessage
from rag.gst_rag import GSTRegulationsRAG
from utils.data_loaders import GSTRateSchedule, HSNSACMaster


class GSTAgentLLM:
    """
    LLM-powered GST validation agent
    
    Combines:
    - Rule-based checks (GSTIN format, etc.)
    - Tax calculation validation (amounts vs rates)
    - RAG retrieval (GST regulations)
    - LLM reasoning (ambiguous cases, RCM determination)
    """

    # def __init__(self, model_name: str = "gpt-4o-mini"):
    #     self.llm = ChatOpenAI(model=model_name, temperature=0)

    def __init__(self, model_name: str = "LLAMA_70B"):
        self.llm = get_llm(model=model_name, temperature=0)
        self.rag = GSTRegulationsRAG()
        self.gst_rates = GSTRateSchedule()
        self.hsn_master = HSNSACMaster()

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a GST compliance expert AI agent. 
            
Your role is to validate invoice GST compliance and provide detailed reasoning.

You have access to:
1. GST regulations via RAG retrieval
2. GST rate schedules
3. HSN/SAC code master data

When validating:
- Use retrieved regulations to support your decisions
- Cite specific sections when relevant
- Explain ambiguous cases clearly
- Provide confidence scores
- Flag items for human review when uncertain

Be thorough but concise. Focus on compliance issues."""),
            ("human", "{input}")
        ])

    async def validate(self, invoice_data: Dict) -> Dict:
        """
        Validate GST compliance using LLM + RAG

        Args:
            invoice_data: Invoice dictionary

        Returns:
            Validation result with checks and reasoning
        """

        checks = []

        # 1. Rule-based checks (fast, deterministic)
        checks.extend(await self._rule_based_checks(invoice_data))

        # 2. Tax calculation validation (CORE REQUIREMENT)
        checks.extend(await self._validate_tax_calculations(invoice_data))

        # 3. LLM-powered checks for complex cases
        if self._needs_llm_reasoning(invoice_data):
            llm_checks = await self._llm_reasoning_checks(invoice_data)
            checks.extend(llm_checks)

        # Aggregate results
        return {
            "category": "B",
            "category_name": "GST Compliance",
            "checks": checks,
            "agent_type": "llm_powered",
            "llm_used": self._needs_llm_reasoning(invoice_data)
        }

    async def _validate_tax_calculations(self, invoice_data: Dict) -> List[Dict]:
        """
        CORE REQUIREMENT: Calculate expected tax and validate against invoice
        """
        checks = []

        # Get line items
        line_items = invoice_data.get('line_items', [])
        if not line_items:
            # Fallback to invoice-level data
            line_items = [{
                'hsn_sac': invoice_data.get('hsn_code', ''),
                'taxable_amount': invoice_data.get('taxable_amount', 0),
                'description': invoice_data.get('description', '')
            }]

        # Determine if interstate or intrastate
        seller_state = invoice_data.get('seller_gstin', '')[:2]
        buyer_state = invoice_data.get('buyer_gstin', '')[:2]
        is_interstate = seller_state != buyer_state

        # Calculate expected tax for each line item
        total_expected_cgst = 0
        total_expected_sgst = 0
        total_expected_igst = 0
        calculation_details = []

        for item in line_items:
            hsn_sac = item.get('hsn_sac', item.get('hsn_code', ''))
            taxable_amount = float(item.get('taxable_amount', item.get('amount', 0)))

            # Get GST rate from master data
            gst_rate = self._get_gst_rate(
                hsn_sac,
                item.get('description', ''),
                invoice_date=invoice_data.get('invoice_date')
            )

            if is_interstate:
                # IGST = full GST rate
                expected_igst = taxable_amount * gst_rate / 100
                total_expected_igst += expected_igst

                calculation_details.append({
                    'item': item.get('description', hsn_sac),
                    'taxable_amount': taxable_amount,
                    'gst_rate': gst_rate,
                    'igst': expected_igst
                })
            else:
                # CGST = SGST = GST rate / 2
                half_rate = gst_rate / 2
                expected_cgst = taxable_amount * half_rate / 100
                expected_sgst = taxable_amount * half_rate / 100

                total_expected_cgst += expected_cgst
                total_expected_sgst += expected_sgst

                calculation_details.append({
                    'item': item.get('description', hsn_sac),
                    'taxable_amount': taxable_amount,
                    'gst_rate': gst_rate,
                    'cgst': expected_cgst,
                    'sgst': expected_sgst
                })

        # Compare with invoice amounts
        tolerance = 0.50  # 50 paise tolerance for rounding differences

        if is_interstate:
            # Validate IGST
            invoice_igst = float(invoice_data.get('igst_amount', invoice_data.get('igst', 0)))
            igst_diff = abs(invoice_igst - total_expected_igst)

            if igst_diff <= tolerance:
                checks.append({
                    "check_id": "B2",
                    "check_name": "IGST Calculation (Interstate)",
                    "status": "PASS",
                    "confidence": 1.0,
                    "reasoning": f"IGST correct: Invoice ₹{invoice_igst:.2f} vs Expected ₹{total_expected_igst:.2f}",
                    "severity": "CRITICAL",
                    "requires_review": False,
                    "agent_type": "rule_based",
                    "calculation_details": calculation_details
                })
            else:
                checks.append({
                    "check_id": "B2",
                    "check_name": "IGST Calculation (Interstate)",
                    "status": "FAIL",
                    "confidence": 1.0,
                    "reasoning": f"IGST mismatch: Invoice ₹{invoice_igst:.2f} vs Expected ₹{total_expected_igst:.2f} (Difference: ₹{igst_diff:.2f})",
                    "severity": "CRITICAL",
                    "requires_review": True,
                    "agent_type": "rule_based",
                    "calculation_details": calculation_details
                })

            # Verify no CGST/SGST for interstate
            invoice_cgst = float(invoice_data.get('cgst_amount', invoice_data.get('cgst', 0)))
            invoice_sgst = float(invoice_data.get('sgst_amount', invoice_data.get('sgst', 0)))

            if invoice_cgst > 0.01 or invoice_sgst > 0.01:
                checks.append({
                    "check_id": "B3",
                    "check_name": "Invalid CGST/SGST in Interstate",
                    "status": "FAIL",
                    "confidence": 1.0,
                    "reasoning": f"Interstate supply should not have CGST/SGST. Found CGST: ₹{invoice_cgst:.2f}, SGST: ₹{invoice_sgst:.2f}",
                    "severity": "CRITICAL",
                    "requires_review": True,
                    "agent_type": "rule_based"
                })

        else:
            # Validate CGST and SGST
            invoice_cgst = float(invoice_data.get('cgst_amount', invoice_data.get('cgst', 0)))
            invoice_sgst = float(invoice_data.get('sgst_amount', invoice_data.get('sgst', 0)))

            cgst_diff = abs(invoice_cgst - total_expected_cgst)
            sgst_diff = abs(invoice_sgst - total_expected_sgst)

            if cgst_diff <= tolerance and sgst_diff <= tolerance:
                checks.append({
                    "check_id": "B4",
                    "check_name": "CGST/SGST Calculation (Intrastate)",
                    "status": "PASS",
                    "confidence": 1.0,
                    "reasoning": f"Tax correct: CGST ₹{invoice_cgst:.2f} vs ₹{total_expected_cgst:.2f}, SGST ₹{invoice_sgst:.2f} vs ₹{total_expected_sgst:.2f}",
                    "severity": "CRITICAL",
                    "requires_review": False,
                    "agent_type": "rule_based",
                    "calculation_details": calculation_details
                })
            else:
                issues = []
                if cgst_diff > tolerance:
                    issues.append(f"CGST: ₹{invoice_cgst:.2f} vs Expected ₹{total_expected_cgst:.2f}")
                if sgst_diff > tolerance:
                    issues.append(f"SGST: ₹{invoice_sgst:.2f} vs Expected ₹{total_expected_sgst:.2f}")

                checks.append({
                    "check_id": "B4",
                    "check_name": "CGST/SGST Calculation (Intrastate)",
                    "status": "FAIL",
                    "confidence": 1.0,
                    "reasoning": f"Tax mismatch: {', '.join(issues)}",
                    "severity": "CRITICAL",
                    "requires_review": True,
                    "agent_type": "rule_based",
                    "calculation_details": calculation_details
                })

            # Verify CGST = SGST
            if abs(invoice_cgst - invoice_sgst) > tolerance:
                checks.append({
                    "check_id": "B5",
                    "check_name": "CGST = SGST Check",
                    "status": "FAIL",
                    "confidence": 1.0,
                    "reasoning": f"CGST and SGST must be equal. CGST: ₹{invoice_cgst:.2f}, SGST: ₹{invoice_sgst:.2f}",
                    "severity": "HIGH",
                    "requires_review": True,
                    "agent_type": "rule_based"
                })

            # Verify no IGST for intrastate
            invoice_igst = float(invoice_data.get('igst_amount', invoice_data.get('igst', 0)))
            if invoice_igst > 0.01:
                checks.append({
                    "check_id": "B6",
                    "check_name": "Invalid IGST in Intrastate",
                    "status": "FAIL",
                    "confidence": 1.0,
                    "reasoning": f"Intrastate supply should not have IGST. Found: ₹{invoice_igst:.2f}",
                    "severity": "CRITICAL",
                    "requires_review": True,
                    "agent_type": "rule_based"
                })

        # Validate total_tax if present
        total_tax_invoice = invoice_data.get('total_tax')
        if total_tax_invoice is not None:
            expected_total_tax = total_expected_igst if is_interstate else (total_expected_cgst + total_expected_sgst)
            total_diff = abs(float(total_tax_invoice) - expected_total_tax)

            if total_diff > tolerance:
                checks.append({
                    "check_id": "B7",
                    "check_name": "Total Tax Validation",
                    "status": "FAIL",
                    "confidence": 1.0,
                    "reasoning": f"Total tax mismatch: Invoice ₹{total_tax_invoice:.2f} vs Expected ₹{expected_total_tax:.2f}",
                    "severity": "CRITICAL",
                    "requires_review": True,
                    "agent_type": "rule_based"
                })

        return checks

    def _get_gst_rate(self, hsn_sac: str, description: str = "", invoice_date=None) -> float:
        """
        Get GST rate for HSN/SAC code from master data or RAG
        """
        # Try to get from rate schedule
        if invoice_date:
            try:
                rate_info = self.gst_rates.get_rate(hsn_sac, invoice_date)
                if rate_info:
                    # Return total GST rate (CGST + SGST or IGST)
                    return rate_info.get('igst', rate_info.get('cgst', 0) + rate_info.get('sgst', 0))
            except Exception as e:
                print(f"⚠️  Error getting GST rate from schedule: {e}")

        # Try HSN master data
        try:
            hsn_info = self.hsn_master.lookup(hsn_sac)
            if hsn_info and 'gst_rate' in hsn_info:
                return hsn_info['gst_rate']
        except:
            pass

        # Fallback: Use RAG to find rate
        # This queries your GST regulations documents
        try:
            context = self.rag.get_context(f"GST rate for HSN {hsn_sac} {description}", k=2)

            # Try to extract rate from context
            import re
            rate_pattern = r'(\d+(?:\.\d+)?)\s*%'
            matches = re.findall(rate_pattern, context)

            if matches:
                # Return the most common rate mentioned
                rates = [float(m) for m in matches]
                return max(set(rates), key=rates.count)
        except:
            pass

        # Default rate (should log warning in production)
        print(f"⚠️  GST rate not found for HSN/SAC: {hsn_sac}, using default 18%")
        return 18.0  # Default GST rate

    async def _rule_based_checks(self, invoice_data: Dict) -> List[Dict]:
        """Fast rule-based GST checks"""

        checks = []

        # GSTIN format check
        import re
        pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9]{1}[Z]{1}[0-9A-Z]{1}$'

        seller_valid = bool(re.match(pattern, invoice_data.get('seller_gstin', '')))
        buyer_valid = bool(re.match(pattern, invoice_data.get('buyer_gstin', '')))

        if seller_valid and buyer_valid:
            checks.append({
                "check_id": "B1",
                "check_name": "GSTIN Format Validation",
                "status": "PASS",
                "confidence": 1.0,
                "reasoning": "Both GSTINs match required format",
                "severity": "CRITICAL",
                "requires_review": False,
                "agent_type": "rule_based"
            })
        else:
            checks.append({
                "check_id": "B1",
                "check_name": "GSTIN Format Validation",
                "status": "FAIL",
                "confidence": 1.0,
                "reasoning": f"GSTIN format invalid - Seller: {seller_valid}, Buyer: {buyer_valid}",
                "severity": "CRITICAL",
                "requires_review": True,
                "agent_type": "rule_based"
            })

        # Interstate/Intrastate check
        seller_state = invoice_data.get('seller_gstin', '')[:2]
        buyer_state = invoice_data.get('buyer_gstin', '')[:2]
        is_interstate = seller_state != buyer_state

        has_igst = invoice_data.get('igst_amount', 0) > 0
        has_cgst_sgst = (invoice_data.get('cgst_amount', 0) > 0 or
                         invoice_data.get('sgst_amount', 0) > 0)

        correct_tax_type = (is_interstate and has_igst) or (not is_interstate and has_cgst_sgst)

        if correct_tax_type:
            checks.append({
                "check_id": "B8",
                "check_name": "Interstate vs Intrastate",
                "status": "PASS",
                "confidence": 1.0,
                "reasoning": f"{'Interstate' if is_interstate else 'Intrastate'} - correct tax type applied",
                "severity": "HIGH",
                "requires_review": False,
                "agent_type": "rule_based"
            })
        else:
            checks.append({
                "check_id": "B8",
                "check_name": "Interstate vs Intrastate",
                "status": "FAIL",
                "confidence": 0.95,
                "reasoning": f"Tax type mismatch - {'Interstate' if is_interstate else 'Intrastate'} but wrong GST applied",
                "severity": "CRITICAL",
                "requires_review": True,
                "agent_type": "rule_based"
            })

        return checks

    def _needs_llm_reasoning(self, invoice_data: Dict) -> bool:
        """Determine if LLM reasoning is needed"""

        # Use LLM for:
        # - Multiple line items with different HSN codes
        # - Reverse charge mechanism determination
        # - Composite supply classification
        # - Ambiguous HSN/SAC descriptions

        line_items = invoice_data.get('line_items', [])

        if len(line_items) > 3:
            return True

        if invoice_data.get('reverse_charge', False):
            return True

        # Check for keywords indicating complex cases
        descriptions = [item.get('description', '').lower() for item in line_items]
        complex_keywords = ['transport', 'warehouse', 'packing', 'composite', 'bundle']

        if any(keyword in desc for desc in descriptions for keyword in complex_keywords):
            return True

        return False

    async def _llm_reasoning_checks(self, invoice_data: Dict) -> List[Dict]:
        """LLM-powered checks for complex cases"""

        checks = []

        # Get relevant regulations from RAG
        line_items = invoice_data.get('line_items', [])
        query = f"GST compliance for invoice with items: {', '.join([item.get('description', '') for item in line_items])}"

        context = self.rag.get_context(query, k=3)

        # Build LLM input
        llm_input = f"""
Analyze this invoice for GST compliance:

Invoice Details:
- Seller GSTIN: {invoice_data.get('seller_gstin')}
- Buyer GSTIN: {invoice_data.get('buyer_gstin')}
- Invoice Date: {invoice_data.get('invoice_date')}
- Total Amount: Rs. {invoice_data.get('total_amount')}

Line Items:
{self._format_line_items(line_items)}

Tax Applied:
- CGST: Rs. {invoice_data.get('cgst_amount', 0)}
- SGST: Rs. {invoice_data.get('sgst_amount', 0)}
- IGST: Rs. {invoice_data.get('igst_amount', 0)}

Relevant GST Regulations:
{context}

Please analyze:
1. Is the HSN/SAC classification appropriate?
2. Is this a composite supply requiring special treatment?
3. Should Reverse Charge Mechanism apply?
4. Are there any GST compliance concerns?

Provide structured analysis with confidence scores.
"""

        # Get LLM response
        chain = self.prompt | self.llm
        response = await chain.ainvoke({"input": llm_input})

        # Parse LLM response and create check
        checks.append({
            "check_id": "B10",
            "check_name": "Complex GST Compliance Analysis",
            "status": self._extract_status(response.content),
            "confidence": 0.85,  # LLM confidence
            "reasoning": response.content[:500],  # Truncate for storage
            "severity": "HIGH",
            "requires_review": True,  # Always review LLM decisions
            "agent_type": "llm_powered"
        })

        return checks

    def _format_line_items(self, line_items: List[Dict]) -> str:
        """Format line items for LLM"""
        formatted = []
        for i, item in enumerate(line_items, 1):
            formatted.append(
                f"{i}. {item.get('description')} - "
                f"HSN/SAC: {item.get('hsn_sac')} - "
                f"Amount: Rs. {item.get('amount')}"
            )
        return "\n".join(formatted)

    def _extract_status(self, llm_response: str) -> str:
        """Extract status from LLM response"""
        response_lower = llm_response.lower()

        if 'compliant' in response_lower or 'no concerns' in response_lower:
            return 'PASS'
        elif 'non-compliant' in response_lower or 'violation' in response_lower:
            return 'FAIL'
        else:
            return 'WARNING'


# Create tool for LangGraph
@tool
async def validate_gst_compliance(invoice_data: Dict) -> Dict:
    """
    Validate GST compliance for an invoice using LLM and RAG.

    Args:
        invoice_data: Invoice dictionary with seller/buyer GSTIN, line items, tax amounts

    Returns:
        Validation result with checks, reasoning, and confidence scores
    """
    agent = GSTAgentLLM()
    return await agent.validate(invoice_data)