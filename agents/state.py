"""
LangGraph State Definition for Compliance Workflow
"""

from typing import TypedDict, Annotated, Optional, List, Dict, Any
from datetime import datetime
from operator import add
from langchain_core.messages import BaseMessage


# Routing constants
ROUTE_TO_RESOLVER = "resolver"
ROUTE_TO_REPORTER = "reporter"
ROUTE_END = "end"


class AgentState(TypedDict):
    """
    State for the compliance validation workflow
    
    Fields with Annotated[..., add] accumulate values from parallel nodes
    Fields without annotation use last-write-wins
    """
    
    # Immutable fields (set once, never updated by nodes)
    invoice_id: str
    invoice_data: Dict[str, Any]
    
    # Accumulated fields (multiple nodes can add to these)
    messages: Annotated[List[BaseMessage], add]
    all_checks: Annotated[List[Dict], add]
    ambiguous_cases: Annotated[List[Dict], add]
    escalation_reasons: Annotated[List[str], add]
    errors: Annotated[List[str], add]
    
    # Result fields (one per agent, last-write-wins)
    document_result: Optional[Dict]
    arithmetic_result: Optional[Dict]
    gst_result: Optional[Dict]
    vendor_result: Optional[Dict]
    tds_result: Optional[Dict]
    policy_result: Optional[Dict]
    
    # Counters (accumulated via custom logic in resolver)
    passed_checks: int
    failed_checks: int
    warning_checks: int
    
    # LLM flags
    requires_llm_reasoning: bool
    
    # Decision fields
    escalation_needed: bool
    overall_status: str
    confidence_score: float
    final_decision: Optional[str]
    reasoning: Optional[str]
    
    # Workflow metadata
    processing_started: datetime
    current_stage: str
