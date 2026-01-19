"""
GST Regulations RAG System
Vector store with GST rules, circulars, and case law
"""

import os
from typing import List, Dict, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class GSTRegulationsRAG:
    """
    RAG system for GST regulations
    Stores and retrieves GST rules, notifications, circulars
    """
    
    def __init__(self, persist_directory: str = "./chroma_db/gst"):
        self.persist_directory = persist_directory
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # Try to load existing vector store
        if os.path.exists(persist_directory):
            self.vectorstore = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings
            )
        else:
            # Create new and populate with GST knowledge
            self.vectorstore = None
            self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """Initialize vector store with GST regulations"""
        
        documents = self._get_gst_documents()
        
        # Split documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        splits = text_splitter.split_documents(documents)
        
        # Create vector store
        self.vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
    
    def _get_gst_documents(self) -> List[Document]:
        """Get GST regulation documents"""
        
        # Core GST knowledge base
        gst_knowledge = [
            {
                "content": """
                GST Registration and GSTIN Format:
                - GSTIN is a 15-character unique identification number
                - Format: [State Code (2)][PAN (10)][Entity Number (1)][Z][Checksum (1)]
                - State code must match the state of business registration
                - Every registered person must have a valid GSTIN
                - GSTIN becomes invalid if registration is cancelled or suspended
                """,
                "metadata": {"source": "CGST Act Section 25", "topic": "registration"}
            },
            {
                "content": """
                Interstate vs Intrastate Supply:
                - Interstate: When supplier and recipient are in different states
                - Intrastate: When supplier and recipient are in the same state
                - Interstate supply attracts IGST (Integrated GST)
                - Intrastate supply attracts CGST (Central GST) + SGST (State GST)
                - CGST rate = SGST rate (always equal)
                - IGST rate = CGST rate + SGST rate
                - Determined by location of supplier and place of supply
                """,
                "metadata": {"source": "CGST Act Section 7-10", "topic": "supply"}
            },
            {
                "content": """
                GST Rate Schedule and HSN/SAC:
                - HSN: Harmonized System of Nomenclature (for goods)
                - SAC: Service Accounting Code (for services)
                - GST rates: 0%, 5%, 12%, 18%, 28%
                - Cess applicable on certain luxury and sin goods
                - Rates can change via GST Council notifications
                - Historical rate must be applied based on invoice date
                - Construction services rate changed from 18% to 12% effective April 1, 2019
                """,
                "metadata": {"source": "GST Rate Schedule", "topic": "rates"}
            },
            {
                "content": """
                Reverse Charge Mechanism (RCM):
                - In specific cases, recipient pays GST instead of supplier
                - Applicable under Section 9(3) and 9(4) of CGST Act
                - Common RCM cases:
                  1. GTA (Goods Transport Agency) services
                  2. Legal services by advocates
                  3. Services from unregistered persons (if recipient is registered)
                  4. Import of services
                - RCM invoices show IGST = 0% but recipient must pay GST
                - Supplier should not charge GST on RCM supplies
                """,
                "metadata": {"source": "CGST Act Section 9", "topic": "rcm"}
            },
            {
                "content": """
                E-Invoice and IRN:
                - Mandatory for businesses with turnover > Rs. 5 crore
                - Invoice Registration Number (IRN) is 64-character hash
                - Generated on GST portal (IRP - Invoice Registration Portal)
                - QR code mandatory on e-invoices
                - IRN contains: Supplier GSTIN, Invoice Number, Financial Year, Document Type
                - Once generated, invoice cannot be modified (only cancelled)
                - Valid for B2B invoices, not required for B2C below certain threshold
                """,
                "metadata": {"source": "GST Notification 13/2020", "topic": "e-invoice"}
            },
            {
                "content": """
                Tax Invoice Requirements:
                - Must contain: GSTIN of supplier and recipient
                - Invoice number (unique, sequential)
                - Invoice date
                - Place of supply
                - HSN/SAC code
                - Description of goods/services
                - Quantity and unit
                - Taxable value
                - Tax rate and amount (CGST, SGST, IGST, Cess)
                - Signature of authorized signatory
                """,
                "metadata": {"source": "CGST Rule 46", "topic": "invoice"}
            },
            {
                "content": """
                Composite Supply and Mixed Supply:
                - Composite Supply: Multiple supplies bundled, one is principal
                  Example: Hotel room with breakfast - principal is accommodation
                  Tax rate: Determined by principal supply
                - Mixed Supply: Multiple independent supplies bundled
                  Example: Gift basket with different items
                  Tax rate: Highest rate among all supplies
                - Logistics with transportation, warehousing, packing is composite
                - Principal supply determination requires case-by-case analysis
                """,
                "metadata": {"source": "CGST Act Section 2(30), 2(74)", "topic": "composite"}
            },
            {
                "content": """
                Input Tax Credit (ITC):
                - Registered person can claim credit of GST paid on inputs
                - Conditions: Used for business purposes, in possession of valid invoice
                - ITC cannot be claimed on certain blocked items (motor vehicles, food, personal use)
                - Time limit: Earlier of - Return for September of next FY OR annual return
                - Reversal required if goods used for non-business purposes
                - ITC on capital goods can be claimed in full in month of receipt
                """,
                "metadata": {"source": "CGST Act Section 16-18", "topic": "itc"}
            }
        ]
        
        documents = [
            Document(
                page_content=doc["content"],
                metadata=doc["metadata"]
            )
            for doc in gst_knowledge
        ]
        
        return documents
    
    def retrieve(self, query: str, k: int = 4) -> List[Document]:
        """
        Retrieve relevant GST regulation documents
        
        Args:
            query: Search query
            k: Number of documents to retrieve
            
        Returns:
            List of relevant documents
        """
        if not self.vectorstore:
            return []
        
        results = self.vectorstore.similarity_search(query, k=k)
        return results
    
    def retrieve_with_scores(self, query: str, k: int = 4) -> List[tuple]:
        """
        Retrieve documents with relevance scores
        
        Returns:
            List of (document, score) tuples
        """
        if not self.vectorstore:
            return []
        
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        return results
    
    def get_context(self, query: str, k: int = 3) -> str:
        """
        Get formatted context string for LLM
        
        Args:
            query: Search query
            k: Number of documents
            
        Returns:
            Formatted context string
        """
        docs = self.retrieve(query, k=k)
        
        if not docs:
            return "No relevant GST regulations found."
        
        context_parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get('source', 'Unknown')
            context_parts.append(
                f"[Regulation {i} - {source}]\n{doc.page_content}\n"
            )
        
        return "\n".join(context_parts)
    
    def add_documents(self, documents: List[Document]):
        """Add new documents to the vector store"""
        if self.vectorstore:
            self.vectorstore.add_documents(documents)
    
    def clear(self):
        """Clear the vector store"""
        if os.path.exists(self.persist_directory):
            import shutil
            shutil.rmtree(self.persist_directory)
            self.vectorstore = None
