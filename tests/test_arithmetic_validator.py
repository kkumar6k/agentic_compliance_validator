"""
Sample test for arithmetic validator

Run with: pytest tests/test_arithmetic_validator.py -v
"""

import pytest
from datetime import date
from models.invoice import InvoiceData, LineItem
from validators.arithmetic_validator import ArithmeticValidator


class TestArithmeticValidator:
    """Test arithmetic validation"""
    
    @pytest.fixture
    def validator(self):
        return ArithmeticValidator()
    
    @pytest.fixture
    def valid_invoice(self):
        """Create a valid test invoice"""
        return InvoiceData(
            invoice_number="TEST-001",
            invoice_date=date(2024, 9, 15),
            seller_name="Test Seller",
            seller_gstin="27AABCT1234F1ZP",
            buyer_name="Test Buyer",
            buyer_gstin="27AABCF9999K1ZX",
            line_items=[
                LineItem(
                    description="Test Item",
                    hsn_sac="998315",
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
    
    @pytest.mark.asyncio
    async def test_valid_invoice_passes(self, validator, valid_invoice):
        """Test that valid invoice passes all checks"""
        
        result = await validator.validate(valid_invoice)
        
        assert result.category == 'C'
        assert result.failed_count == 0
        assert result.passed_count > 0
    
    @pytest.mark.asyncio
    async def test_incorrect_subtotal_fails(self, validator, valid_invoice):
        """Test that incorrect subtotal is detected"""
        
        # Break the subtotal
        valid_invoice.subtotal = 99999
        
        result = await validator.validate(valid_invoice)
        
        # Should have at least one failure
        assert result.failed_count > 0
        
        # Check that C2 (subtotal) failed
        c2_check = next(c for c in result.checks if c.check_id == 'C2')
        assert c2_check.status.value == 'FAIL'
    
    @pytest.mark.asyncio
    async def test_incorrect_total_fails(self, validator, valid_invoice):
        """Test that incorrect total is detected"""
        
        # Break the total
        valid_invoice.total_amount = 120000
        
        result = await validator.validate(valid_invoice)
        
        # Check that C10 (total) failed
        c10_check = next(c for c in result.checks if c.check_id == 'C10')
        assert c10_check.status.value == 'FAIL'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
