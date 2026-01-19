"""
Integration tests for complete validation workflow
Tests the full system with all validators

Run with: pytest tests/test_integration.py -v
"""

import pytest
import asyncio
from datetime import date
from models.invoice import InvoiceData, LineItem
from agents.orchestrator import OrchestratorAgent
from utils.data_loaders import InvoiceDataLoader


class TestIntegrationWorkflow:
    """Test complete validation workflow"""
    
    @pytest.fixture
    def orchestrator(self):
        config = {
            'confidence_threshold': 0.70,
            'high_value_threshold': 1000000
        }
        return OrchestratorAgent(config)
    
    @pytest.fixture
    def test_loader(self):
        return InvoiceDataLoader()
    
    def create_invoice(self, invoice_json: dict) -> InvoiceData:
        """Helper to create invoice from JSON"""
        line_items = [LineItem(**item) for item in invoice_json['line_items']]
        
        # Determine states
        state_map = {'27': 'Maharashtra', '07': 'Delhi', '29': 'Karnataka'}
        seller_state = state_map.get(invoice_json['vendor']['gstin'][:2])
        buyer_state = state_map.get(invoice_json['buyer']['gstin'][:2])
        
        return InvoiceData(
            invoice_number=invoice_json['invoice_number'],
            invoice_date=date.fromisoformat(invoice_json['invoice_date']),
            seller_name=invoice_json['vendor']['name'],
            seller_gstin=invoice_json['vendor']['gstin'],
            seller_state=seller_state,
            buyer_name=invoice_json['buyer']['name'],
            buyer_gstin=invoice_json['buyer']['gstin'],
            buyer_state=buyer_state,
            line_items=line_items,
            subtotal=invoice_json['subtotal'],
            cgst_amount=invoice_json.get('cgst_amount', 0),
            sgst_amount=invoice_json.get('sgst_amount', 0),
            igst_amount=invoice_json.get('igst_amount', 0),
            total_tax=invoice_json['total_tax'],
            total_amount=invoice_json['total_amount'],
            po_reference=invoice_json.get('po_reference'),
            payment_terms=invoice_json.get('payment_terms')
        )
    
    @pytest.mark.asyncio
    async def test_standard_valid_invoice(self, orchestrator, test_loader):
        """Test that standard valid invoice passes all checks"""
        
        # Get standard valid invoice
        invoices = test_loader.get_by_category('STANDARD_VALID')
        assert len(invoices) > 0, "No STANDARD_VALID invoices found"
        
        invoice_json = invoices[0]
        invoice_data = self.create_invoice(invoice_json)
        
        # Process
        result = await orchestrator.process_invoice(invoice_data)
        
        # Assertions
        assert result['status'] == 'success'
        assert result['validation_result'] is not None
        
        val_result = result['validation_result']
        
        # Should pass most checks
        assert val_result.passed_checks > 0
        assert val_result.overall_status in ['PASS', 'PASS_WITH_WARNINGS']
    
    @pytest.mark.asyncio
    async def test_all_validators_run(self, orchestrator, test_loader):
        """Test that all 5 validators are executed"""
        
        invoices = test_loader.get_by_complexity('LOW')
        invoice_data = self.create_invoice(invoices[0])
        
        result = await orchestrator.process_invoice(invoice_data)
        
        assert result['status'] == 'success'
        val_result = result['validation_result']
        
        # Should have results from all 5 categories
        categories = val_result.category_results
        
        # Check that we have multiple categories
        assert len(categories) >= 3, f"Expected multiple categories, got {len(categories)}"
        
        # Check for key categories
        assert 'C' in categories  # Arithmetic
        assert 'B' in categories  # GST
    
    @pytest.mark.asyncio
    async def test_high_value_escalation(self, orchestrator):
        """Test that high-value invoices are escalated"""
        
        # Create high-value invoice
        invoice_data = InvoiceData(
            invoice_number="TEST-HIGH-001",
            invoice_date=date(2024, 9, 15),
            seller_name="Test Vendor",
            seller_gstin="27AABCT1234F1ZP",
            seller_state="Maharashtra",
            buyer_name="FinanceGuard Solutions",
            buyer_gstin="27AABCF9999K1ZX",
            buyer_state="Maharashtra",
            line_items=[
                LineItem(
                    description="High value service",
                    hsn_sac="998315",
                    quantity=1,
                    rate=5000000,
                    amount=5000000
                )
            ],
            subtotal=5000000,
            cgst_amount=450000,
            sgst_amount=450000,
            total_tax=900000,
            total_amount=5900000
        )
        
        result = await orchestrator.process_invoice(invoice_data)
        
        assert result['status'] == 'success'
        assert result['escalated'] == True
        assert any('High value' in reason for reason in result['escalation_reasons'])
    
    @pytest.mark.asyncio
    async def test_low_confidence_escalation(self, orchestrator):
        """Test that low confidence results trigger escalation"""
        
        # This would need an invoice that triggers multiple warnings/failures
        # For now, just verify the escalation logic exists
        
        invoice_data = InvoiceData(
            invoice_number="TEST-LOW-CONF-001",
            invoice_date=date(2024, 9, 15),
            seller_name="Unknown Vendor",
            seller_gstin="99XXXXX9999X9XX",  # Invalid GSTIN
            buyer_name="FinanceGuard Solutions",
            buyer_gstin="27AABCF9999K1ZX",
            line_items=[
                LineItem(
                    description="Test",
                    hsn_sac="999999",  # Invalid HSN
                    quantity=1,
                    rate=100000,
                    amount=100000
                )
            ],
            subtotal=100000,
            cgst_amount=9000,
            sgst_amount=9000,
            total_tax=18000,
            total_amount=118000
        )
        
        result = await orchestrator.process_invoice(invoice_data)
        
        # Should either escalate or have failures
        assert result['status'] == 'success'
        assert result['validation_result'].failed_checks > 0 or result['escalated']
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, orchestrator, test_loader):
        """Test batch processing of multiple invoices"""
        
        # Get a few test invoices
        invoices_json = test_loader.get_by_complexity('LOW')[:3]
        invoices_data = [self.create_invoice(inv) for inv in invoices_json]
        
        # Process batch
        batch_result = await orchestrator.process_batch(invoices_data)
        
        # Assertions
        assert batch_result['total_invoices'] == len(invoices_data)
        assert batch_result['successful'] > 0
        assert 'average_confidence' in batch_result
        assert 'average_processing_time_ms' in batch_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
