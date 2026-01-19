"""
TDS Regulations RAG System
Vector store with TDS rules and regulations
"""

import os
from typing import List
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class TDSRegulationsRAG:
    """
    RAG system for TDS regulations
    Stores and retrieves TDS rules, sections, rates
    """
    
    def __init__(self, persist_directory: str = "./chroma_db/tds"):
        self.persist_directory = persist_directory
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        if os.path.exists(persist_directory):
            self.vectorstore = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings
            )
        else:
            self.vectorstore = None
            self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """Initialize vector store with TDS regulations"""
        
        documents = self._get_tds_documents()
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
        )
        
        splits = text_splitter.split_documents(documents)
        
        self.vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
    
    def _get_tds_documents(self) -> List[Document]:
        """Get TDS regulation documents"""
        
        tds_knowledge = [
            {
                "content": """
                Section 194C - Payments to Contractors:
                - Applicable on payments for carrying out any work (including supply of labour)
                - Rate: 1% for individual/HUF contractors with PAN, 2% for others
                - Rate: 2% for corporate contractors
                - Single payment threshold: Rs. 30,000
                - Aggregate threshold: Rs. 1,00,000 in a financial year
                - TDS must be deducted at the time of credit or payment, whichever is earlier
                - Applies to civil construction, repairs, advertising contracts, etc.
                - Does NOT apply to transport contractors (see 194C separately)
                """,
                "metadata": {"source": "Section 194C", "section": "194C"}
            },
            {
                "content": """
                Section 194J - Professional or Technical Services:
                - Covers professional services, technical services, royalty, non-compete fees
                - Rate: 2% for professional/technical services (if payee has PAN)
                - Rate: 10% for fees for technical services, royalty, non-compete
                - Threshold: Rs. 30,000 per transaction
                - Applies to: CA, lawyers, doctors, engineers, architects, IT professionals
                - Technical services include software development, IT consulting
                - Must deduct on payment or credit, whichever is earlier
                - No threshold for directors' fees
                """,
                "metadata": {"source": "Section 194J", "section": "194J"}
            },
            {
                "content": """
                Section 194H - Commission and Brokerage:
                - Applicable on commission or brokerage payments
                - Rate: 5% (if payee has PAN)
                - Threshold: Rs. 15,000 per transaction
                - Commission includes any payment for services in relation to sale/purchase
                - Brokerage includes any payment for services of a broker or agent
                - Excludes insurance commission (covered under 194D)
                - Applies to real estate brokers, stock brokers, sales agents, etc.
                """,
                "metadata": {"source": "Section 194H", "section": "194H"}
            },
            {
                "content": """
                Section 194I - Rent:
                - Covers rent payments for plant & machinery, equipment, land, building, furniture
                - Rate: 2% for plant/machinery/equipment
                - Rate: 10% for land, building, furniture
                - Threshold: Rs. 2,40,000 per year
                - IMPORTANT: TDS on rent is calculated on GROSS rent (including GST)
                - Must deduct monthly if rent exceeds threshold
                - Applies to both short-term and long-term leases
                - Even residential rent is covered if for business use
                """,
                "metadata": {"source": "Section 194I", "section": "194I"}
            },
            {
                "content": """
                Section 194Q - Purchase of Goods:
                - Introduced from July 1, 2021
                - Applicable when buyer's turnover exceeds Rs. 10 crore
                - Rate: 0.1% on purchase value exceeding Rs. 50 lakhs from single seller
                - Applies to purchase of goods only, not services
                - TDS deducted at time of credit or payment
                - Seller can claim this as TDS credit in their return
                - Both buyer and seller must have valid PAN/TAN
                """,
                "metadata": {"source": "Section 194Q", "section": "194Q"}
            },
            {
                "content": """
                Section 195 - Payments to Non-Residents:
                - Covers any payment to non-resident (not being a company) or foreign company
                - Rate: Varies by type of payment and tax treaty
                - Common rates: 10-40% depending on nature of income
                - Includes royalty, fees for technical services, interest, rent
                - Must obtain PAN or withhold at maximum marginal rate
                - Tax treaty relief can be claimed if applicable
                - Form 15CA/15CB required for remittances
                """,
                "metadata": {"source": "Section 195", "section": "195"}
            },
            {
                "content": """
                Section 206AB - Higher TDS for Non-Filers:
                - Effective from July 1, 2021
                - Applicable to specified persons who have not filed ITR
                - Specified person: One who has not filed returns for 2 preceding years
                  AND aggregate TDS/TCS in each year was Rs. 50,000 or more
                - Rate: Higher of - (a) 2x normal TDS rate, OR (b) 5%
                - Very important to check 206AB status before determining TDS rate
                - Can significantly increase TDS liability
                - TRACES portal can be checked for 206AB status
                """,
                "metadata": {"source": "Section 206AB", "section": "206AB"}
            },
            {
                "content": """
                TDS Base Amount Calculation:
                - General Rule: TDS calculated on amount EXCLUDING GST
                - Exception: Section 194I (Rent) - TDS on amount INCLUDING GST
                - For contractors (194C): TDS on contract value excluding materials
                  (if materials separately billed)
                - For professionals (194J): TDS on service fee excluding GST
                - Always check invoice bifurcation between service and GST
                - Payment terms don't affect TDS - based on credit or payment date
                - Advance payments also attract TDS
                """,
                "metadata": {"source": "TDS Calculation Rules", "section": "general"}
            },
            {
                "content": """
                Certificate for Lower/Nil Deduction (Form 13):
                - Vendor can apply to Assessing Officer for lower TDS certificate
                - Valid reasons: Loss situation, lower expected income, eligible deductions
                - Certificate specifies: PAN, Deductor, Rate, Valid period, Amount
                - Deductor must verify certificate authenticity on TRACES
                - Overrides normal TDS rates when valid
                - Commonly used by: Startups, exporters, businesses with losses
                - Must be renewed periodically
                """,
                "metadata": {"source": "Section 197", "section": "197"}
            }
        ]
        
        documents = [
            Document(
                page_content=doc["content"],
                metadata=doc["metadata"]
            )
            for doc in tds_knowledge
        ]
        
        return documents
    
    def retrieve(self, query: str, k: int = 3) -> List[Document]:
        """Retrieve relevant TDS documents"""
        if not self.vectorstore:
            return []
        return self.vectorstore.similarity_search(query, k=k)
    
    def get_context(self, query: str, k: int = 3) -> str:
        """Get formatted context for LLM"""
        docs = self.retrieve(query, k=k)
        
        if not docs:
            return "No relevant TDS regulations found."
        
        context_parts = []
        for i, doc in enumerate(docs, 1):
            section = doc.metadata.get('section', 'Unknown')
            context_parts.append(
                f"[TDS Section {section}]\n{doc.page_content}\n"
            )
        
        return "\n".join(context_parts)
