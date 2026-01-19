"""
LangGraph Multi-Agent Workflow
Orchestrates validation using supervisor pattern with specialized agents
"""

from typing import Literal
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import AgentState, ROUTE_TO_RESOLVER, ROUTE_TO_REPORTER, ROUTE_END
from validators.gst_validator import GSTValidator
from validators.arithmetic_validator import ArithmeticValidator
from validators.vendor_validator import VendorValidator
from validators.tds_validator import TDSValidator
from validators.policy_validator import PolicyValidator
from validators.document_validator import DocumentValidator
from utils.data_transformer import transform_invoice_data


class ComplianceWorkflow:
    """
    LangGraph-based compliance validation workflow

    Uses supervisor pattern with specialized validation agents:
    - Document Agent (Category A - authenticity checks)
    - Arithmetic Agent (Category C - rule-based)
    - GST Agent (Category B - LLM + RAG)
    - Vendor Agent (lookups)
    - TDS Agent (Category D - rule-based)
    - Policy Agent (Category E - rule-based)
    - Resolver Agent (LLM for conflicts)
    - Reporter Agent (LLM for reports)
    """

    def __init__(self):
        from utils.llm_factory import get_llm, LLAMA_70B, LLAMA_8B

        self.llm = get_llm(model=LLAMA_70B, temperature=0)
        self.llm_mini = get_llm(model=LLAMA_8B, temperature=0)

        # Initialize agents
        self.document_agent = DocumentValidator()
        self.arithmetic_agent = ArithmeticValidator()
        self.gst_agent = GSTValidator()
        self.vendor_agent = VendorValidator()
        self.tds_agent = TDSValidator()
        self.policy_agent = PolicyValidator()

        # Build graph
        self.graph = self._build_graph()
        self.app = self.graph.compile()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""

        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("supervisor", self.supervisor_node)
        workflow.add_node("document", self.document_node)
        workflow.add_node("arithmetic", self.arithmetic_node)
        workflow.add_node("gst", self.gst_node)
        workflow.add_node("vendor", self.vendor_node)
        workflow.add_node("tds", self.tds_node)
        workflow.add_node("policy", self.policy_node)
        workflow.add_node("resolver", self.resolver_node)
        workflow.add_node("reporter", self.reporter_node)

        # Entry point
        workflow.set_entry_point("supervisor")

        # Supervisor routes to validators (parallel execution)
        workflow.add_edge("supervisor", "document")
        workflow.add_edge("supervisor", "arithmetic")
        workflow.add_edge("supervisor", "gst")
        workflow.add_edge("supervisor", "vendor")
        workflow.add_edge("supervisor", "tds")
        workflow.add_edge("supervisor", "policy")

        # All validators go to resolver
        workflow.add_edge("document", "resolver")
        workflow.add_edge("arithmetic", "resolver")
        workflow.add_edge("gst", "resolver")
        workflow.add_edge("vendor", "resolver")
        workflow.add_edge("tds", "resolver")
        workflow.add_edge("policy", "resolver")

        # Resolver to reporter
        workflow.add_edge("resolver", "reporter")

        # Reporter to end
        workflow.add_edge("reporter", END)

        return workflow

    async def supervisor_node(self, state: AgentState) -> AgentState:
        """
        Supervisor node - initializes validation workflow
        """

        state["processing_started"] = datetime.now()
        state["current_stage"] = "validation"
        state["all_checks"] = []
        state["passed_checks"] = 0
        state["failed_checks"] = 0
        state["warning_checks"] = 0
        state["requires_llm_reasoning"] = False
        state["ambiguous_cases"] = []
        state["escalation_needed"] = False
        state["escalation_reasons"] = []
        state["errors"] = []

        # Add supervisor message
        message = HumanMessage(
            content=f"Starting compliance validation for invoice {state['invoice_id']}"
        )
        state["messages"].append(message)

        return state

    async def document_node(self, state: AgentState) -> AgentState:
        """Document authenticity validation node (Category A)"""

        from models.invoice import InvoiceData, LineItem
        from datetime import date

        # Transform nested structure to flat structure
        inv_data = transform_invoice_data(state["invoice_data"])
        line_items = [LineItem(**item) for item in inv_data.get("line_items", [])]

        invoice = InvoiceData(
            invoice_number=inv_data.get("invoice_number"),
            invoice_date=date.fromisoformat(inv_data.get("invoice_date")),
            seller_name=inv_data.get("seller_name"),
            seller_gstin=inv_data.get("seller_gstin"),
            seller_state=inv_data.get("seller_state"),
            buyer_name=inv_data.get("buyer_name"),
            buyer_gstin=inv_data.get("buyer_gstin"),
            line_items=line_items,
            subtotal=inv_data.get("subtotal"),
            total_amount=inv_data.get("total_amount"),
            irn=inv_data.get("irn"),
            irn_date=date.fromisoformat(inv_data.get("irn_date")) if inv_data.get("irn_date") else None,
            qr_code_present=inv_data.get("qr_code_present", False),
            extraction_confidence=inv_data.get("extraction_confidence", 1.0),
            format_type=inv_data.get("format_type", "json")
        )

        # Run validation
        result = await self.document_agent.validate(invoice, state)

        # Create result dict (don't modify state)
        document_result = {
            "category": result.category,
            "checks": [
                {
                    "check_id": c.check_id,
                    "check_name": c.check_name,
                    "status": c.status.value,
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                    "severity": c.severity.value,
                    "requires_review": c.requires_review
                }
                for c in result.checks
            ]
        }

        # Return only the fields this node modifies
        return {
            "document_result": document_result,
            "all_checks": document_result["checks"]
        }

    async def arithmetic_node(self, state: AgentState) -> AgentState:
        """Arithmetic validation node (rule-based)"""

        from models.invoice import InvoiceData, LineItem
        from datetime import date

        # Transform nested structure to flat structure
        inv_data = transform_invoice_data(state["invoice_data"])
        line_items = [LineItem(**item) for item in inv_data.get("line_items", [])]

        invoice = InvoiceData(
            invoice_number=inv_data.get("invoice_number"),
            invoice_date=date.fromisoformat(inv_data.get("invoice_date")),
            seller_name=inv_data.get("seller_name"),
            seller_gstin=inv_data.get("seller_gstin"),
            buyer_name=inv_data.get("buyer_name"),
            buyer_gstin=inv_data.get("buyer_gstin"),
            line_items=line_items,
            subtotal=inv_data.get("subtotal"),
            cgst_amount=inv_data.get("cgst_amount", 0),
            sgst_amount=inv_data.get("sgst_amount", 0),
            igst_amount=inv_data.get("igst_amount", 0),
            total_tax=inv_data.get("total_tax"),
            total_amount=inv_data.get("total_amount")
        )

        # Run validation
        result = await self.arithmetic_agent.validate(invoice)

        # Create result dict (don't modify state)
        arithmetic_result = {
            "category": result.category,
            "checks": [
                {
                    "check_id": c.check_id,
                    "check_name": c.check_name,
                    "status": c.status.value,
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                    "severity": c.severity.value,
                    "requires_review": c.requires_review
                }
                for c in result.checks
            ]
        }

        # Return only modified fields
        return {
            "arithmetic_result": arithmetic_result,
            "all_checks": arithmetic_result["checks"]
        }

    async def gst_node(self, state: AgentState) -> AgentState:
        """GST validation node (Category B - comprehensive 18 checks)"""

        from models.invoice import InvoiceData, LineItem
        from datetime import date

        # Transform nested structure to flat structure
        inv_data = transform_invoice_data(state["invoice_data"])
        line_items = [LineItem(**item) for item in inv_data.get("line_items", [])]

        invoice = InvoiceData(
            invoice_number=inv_data.get("invoice_number"),
            invoice_date=date.fromisoformat(inv_data.get("invoice_date")),
            seller_name=inv_data.get("seller_name"),
            seller_gstin=inv_data.get("seller_gstin"),
            seller_state=inv_data.get("seller_state"),
            buyer_name=inv_data.get("buyer_name"),
            buyer_gstin=inv_data.get("buyer_gstin"),
            line_items=line_items,
            subtotal=inv_data.get("subtotal"),
            cgst_amount=inv_data.get("cgst_amount", 0),
            sgst_amount=inv_data.get("sgst_amount", 0),
            igst_amount=inv_data.get("igst_amount", 0),
            total_tax=inv_data.get("total_tax"),
            total_amount=inv_data.get("total_amount"),
            place_of_supply=inv_data.get("place_of_supply"),
            reverse_charge=inv_data.get("reverse_charge", False),
            irn=inv_data.get("irn"),
            irn_date=date.fromisoformat(inv_data.get("irn_date")) if inv_data.get("irn_date") else None,
            qr_code_present=inv_data.get("qr_code_present", False)
        )

        # Run validation
        result = await self.gst_agent.validate(invoice, state)

        # Create result dict (don't modify state)
        gst_result = {
            "category": result.category,
            "checks": [
                {
                    "check_id": c.check_id,
                    "check_name": c.check_name,
                    "status": c.status.value,
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                    "severity": c.severity.value,
                    "requires_review": c.requires_review
                }
                for c in result.checks
            ]
        }

        # Return only the fields this node modifies
        return {
            "gst_result": gst_result,
            "all_checks": gst_result["checks"]
        }

    async def vendor_node(self, state: AgentState) -> AgentState:
        """Vendor validation node (rule-based + lookups)"""

        from models.invoice import InvoiceData, LineItem
        from datetime import date

        # Transform nested structure to flat structure
        inv_data = transform_invoice_data(state["invoice_data"])
        line_items = [LineItem(**item) for item in inv_data.get("line_items", [])]

        invoice = InvoiceData(
            invoice_number=inv_data.get("invoice_number"),
            invoice_date=date.fromisoformat(inv_data.get("invoice_date")),
            seller_name=inv_data.get("seller_name"),
            seller_gstin=inv_data.get("seller_gstin"),
            buyer_name=inv_data.get("buyer_name"),
            buyer_gstin=inv_data.get("buyer_gstin"),
            line_items=line_items,
            subtotal=inv_data.get("subtotal"),
            total_amount=inv_data.get("total_amount")
        )

        result = await self.vendor_agent.validate(invoice)

        # Create result dict (don't modify state)
        vendor_result = {
            "category": result.category,
            "checks": [
                {
                    "check_id": c.check_id,
                    "check_name": c.check_name,
                    "status": c.status.value,
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                    "severity": c.severity.value,
                    "requires_review": c.requires_review
                }
                for c in result.checks
            ]
        }

        # Return only the fields this node modifies
        return {
            "vendor_result": vendor_result,
            "all_checks": vendor_result["checks"]
        }

    async def tds_node(self, state: AgentState) -> AgentState:
        """TDS validation node (Category D - comprehensive 12 checks)"""

        from models.invoice import InvoiceData, LineItem
        from datetime import date

        # Transform nested structure to flat structure
        inv_data = transform_invoice_data(state["invoice_data"])
        line_items = [LineItem(**item) for item in inv_data.get("line_items", [])]
        line_items = [LineItem(**item) for item in inv_data.get("line_items", [])]

        invoice = InvoiceData(
            invoice_number=inv_data.get("invoice_number"),
            invoice_date=date.fromisoformat(inv_data.get("invoice_date")),
            seller_name=inv_data.get("seller_name"),
            seller_gstin=inv_data.get("seller_gstin"),
            buyer_name=inv_data.get("buyer_name"),
            buyer_gstin=inv_data.get("buyer_gstin"),
            line_items=line_items,
            subtotal=inv_data.get("subtotal"),
            total_amount=inv_data.get("total_amount"),
            cgst_amount=inv_data.get("cgst_amount", 0),
            sgst_amount=inv_data.get("sgst_amount", 0),
            igst_amount=inv_data.get("igst_amount", 0),
            tds_applicable=inv_data.get("tds_applicable", False),
            tds_section=inv_data.get("tds_section"),
            tds_rate=inv_data.get("tds_rate"),
            tds_amount=inv_data.get("tds_amount")
        )

        result = await self.tds_agent.validate(invoice, state)

        # Create result dict (don't modify state)
        tds_result = {
            "category": result.category,
            "checks": [
                {
                    "check_id": c.check_id,
                    "check_name": c.check_name,
                    "status": c.status.value,
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                    "severity": c.severity.value,
                    "requires_review": c.requires_review
                }
                for c in result.checks
            ]
        }

        # Return only the fields this node modifies
        return {
            "tds_result": tds_result,
            "all_checks": tds_result["checks"]
        }

    async def policy_node(self, state: AgentState) -> AgentState:
        """Policy validation node (rule-based)"""

        from models.invoice import InvoiceData, LineItem
        from datetime import date

        # Transform nested structure to flat structure
        inv_data = transform_invoice_data(state["invoice_data"])
        line_items = [LineItem(**item) for item in inv_data.get("line_items", [])]

        invoice = InvoiceData(
            invoice_number=inv_data.get("invoice_number"),
            invoice_date=date.fromisoformat(inv_data.get("invoice_date")),
            seller_name=inv_data.get("seller_name"),
            seller_gstin=inv_data.get("seller_gstin"),
            buyer_name=inv_data.get("buyer_name"),
            buyer_gstin=inv_data.get("buyer_gstin"),
            line_items=line_items,
            subtotal=inv_data.get("subtotal"),
            total_amount=inv_data.get("total_amount"),
            po_reference=inv_data.get("po_reference"),
            payment_terms=inv_data.get("payment_terms")
        )

        result = await self.policy_agent.validate(invoice)

        # Create result dict (don't modify state)
        policy_result = {
            "category": result.category,
            "checks": [
                {
                    "check_id": c.check_id,
                    "check_name": c.check_name,
                    "status": c.status.value,
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                    "severity": c.severity.value,
                    "requires_review": c.requires_review
                }
                for c in result.checks
            ]
        }

        # Return only the fields this node modifies
        return {
            "policy_result": policy_result,
            "all_checks": policy_result["checks"]
        }

    async def resolver_node(self, state: AgentState) -> AgentState:
        """
        Resolver node - uses LLM to analyze results and make final decision
        """

        # Calculate statistics
        for check in state["all_checks"]:
            if check["status"] == "PASS":
                state["passed_checks"] += 1
            elif check["status"] == "FAIL":
                state["failed_checks"] += 1
            elif check["status"] == "WARNING":
                state["warning_checks"] += 1

        # Calculate confidence
        total_checks = len(state["all_checks"])
        if total_checks > 0:
            confidences = [c["confidence"] for c in state["all_checks"]]
            state["confidence_score"] = sum(confidences) / len(confidences)
        else:
            state["confidence_score"] = 0.0

        # Determine escalation
        if state["failed_checks"] >= 3 or state["confidence_score"] < 0.70:
            state["escalation_needed"] = True
            state["escalation_reasons"].append(
                f"{state['failed_checks']} checks failed with {state['confidence_score']:.0%} confidence"
            )

        # Get LLM to analyze complex cases
        if state["requires_llm_reasoning"] or state["failed_checks"] > 0:
            analysis_prompt = f"""
Analyze this invoice validation result and provide final decision:

Total Checks: {total_checks}
Passed: {state['passed_checks']}
Failed: {state['failed_checks']}
Warnings: {state['warning_checks']}
Average Confidence: {state['confidence_score']:.0%}

Failed/Warning Checks:
{self._format_failed_checks(state['all_checks'])}

Provide:
1. Overall compliance status (COMPLIANT / NON-COMPLIANT / REQUIRES_REVIEW)
2. Key reasoning (2-3 sentences)
3. Recommendation for action

Be concise and actionable.
"""

            response = await self.llm_mini.ainvoke([
                SystemMessage(content="You are a compliance decision AI. Be decisive and clear."),
                HumanMessage(content=analysis_prompt)
            ])

            state["final_decision"] = response.content
            state["reasoning"] = response.content[:300]

        # Set overall status
        if state["failed_checks"] == 0:
            state["overall_status"] = "PASS"
        elif state["failed_checks"] <= 2 and state["confidence_score"] > 0.80:
            state["overall_status"] = "PASS_WITH_WARNINGS"
        else:
            state["overall_status"] = "FAIL"

        state["current_stage"] = "resolved"

        return state

    async def reporter_node(self, state: AgentState) -> AgentState:
        """Reporter node - generates final report"""

        state["current_stage"] = "reporting"

        # Report is generated externally using ReporterAgent
        # This node just marks completion

        return state

    def _format_failed_checks(self, all_checks: list) -> str:
        """Format failed/warning checks for LLM"""
        failed = [c for c in all_checks if c["status"] in ["FAIL", "WARNING"]]

        if not failed:
            return "None"

        formatted = []
        for check in failed[:5]:  # Limit to 5
            formatted.append(
                f"- {check['check_id']}: {check['check_name']} - {check['reasoning'][:100]}"
            )

        return "\n".join(formatted)

    async def run(self, invoice_id: str, invoice_data: dict) -> dict:
        """
        Run the complete workflow

        Args:
            invoice_id: Invoice ID
            invoice_data: Invoice data dictionary

        Returns:
            Final state with validation results
        """

        initial_state = AgentState(
            invoice_id=invoice_id,
            invoice_data=invoice_data,
            messages=[],
            document_result=None,
            arithmetic_result=None,
            gst_result=None,
            vendor_result=None,
            tds_result=None,
            policy_result=None,
            all_checks=[],
            passed_checks=0,
            failed_checks=0,
            warning_checks=0,
            requires_llm_reasoning=False,
            ambiguous_cases=[],
            escalation_needed=False,
            escalation_reasons=[],
            overall_status="",
            confidence_score=0.0,
            final_decision=None,
            reasoning=None,
            processing_started=datetime.now(),
            current_stage="init",
            errors=[]
        )

        final_state = await self.app.ainvoke(initial_state)

        return final_state