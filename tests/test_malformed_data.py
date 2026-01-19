"""
Malformed Data Tests
Tests validation layer with various types of malformed/corrupted data
"""

import pytest
from utils.validators import InvoiceValidator, validate_invoice


class TestMalformedDataHandling:
    """Tests that system handles malformed data gracefully"""
    
    def setup_method(self):
        """Setup validator for each test"""
        self.validator = InvoiceValidator()
    
    def test_completely_empty_invoice(self):
        """Test empty dictionary"""
        invoice = {}
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert len(result.errors) > 0
        # Should have error for each missing required field
        assert any("invoice_number" in err for err in result.errors)
        assert any("invoice_date" in err for err in result.errors)
    
    def test_null_values(self):
        """Test None/null values"""
        invoice = {
            "invoice_number": None,
            "invoice_date": None,
            "vendor": None,
            "buyer": None,
            "line_items": None,
            "subtotal": None,
            "total_tax": None,
            "total_amount": None
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert len(result.errors) >= 3  # Multiple structure errors
    
    def test_wrong_data_types(self):
        """Test completely wrong data types"""
        invoice = {
            "invoice_number": 12345,  # Should be string
            "invoice_date": 20240915,  # Should be string
            "vendor": "vendor_string",  # Should be dict
            "buyer": ["buyer", "list"],  # Should be dict
            "line_items": "items_string",  # Should be list
            "subtotal": "one hundred",  # Should be number
            "total_tax": [18],  # Should be number
            "total_amount": {"amount": 118}  # Should be number
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        # Should catch multiple type errors
        assert any("must be" in err for err in result.errors)
    
    def test_negative_amounts(self):
        """Test negative amounts"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": -5, "rate": -100, "amount": -500}
            ],
            "subtotal": -500,
            "total_tax": -90,
            "total_amount": -590
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("negative" in err.lower() or "positive" in err.lower() 
                   for err in result.errors)
    
    def test_zero_amounts(self):
        """Test zero amounts"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": 0, "rate": 0, "amount": 0}
            ],
            "subtotal": 0,
            "total_tax": 0,
            "total_amount": 0
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("positive" in err.lower() for err in result.errors)
    
    def test_extreme_amounts(self):
        """Test unreasonably large amounts"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": 1, "rate": 999999999999, "amount": 999999999999}
            ],
            "subtotal": 999999999999,
            "total_tax": 0,
            "total_amount": 999999999999
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("unreasonably" in err.lower() or "high" in err.lower() 
                   for err in result.errors)
    
    def test_future_date(self):
        """Test invoice dated in future"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2099-12-31",  # Future!
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": 1, "rate": 100, "amount": 100}
            ],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("future" in err.lower() for err in result.errors)
    
    def test_very_old_date(self):
        """Test invoice dated too far in past"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "1990-01-01",  # Too old!
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": 1, "rate": 100, "amount": 100}
            ],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("too old" in err.lower() for err in result.errors)
    
    def test_invalid_date_format(self):
        """Test invalid date format"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "32/13/2024",  # Invalid format
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": 1, "rate": 100, "amount": 100}
            ],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("date" in err.lower() for err in result.errors)
    
    def test_invalid_gstin_formats(self):
        """Test various invalid GSTIN formats"""
        
        invalid_gstins = [
            "123",  # Too short
            "ABCD1234EFGH56789Z1",  # Wrong format
            "27AABCT1234F1Z",  # Missing character
            "99INVALID99999X9X9",  # Invalid format
            "",  # Empty
            "NOT-A-GSTIN",  # Completely wrong
        ]
        
        for bad_gstin in invalid_gstins:
            invoice = {
                "invoice_number": "INV-001",
                "invoice_date": "2024-09-15",
                "vendor": {"name": "Test", "gstin": bad_gstin},
                "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
                "line_items": [
                    {"description": "Item", "quantity": 1, "rate": 100, "amount": 100}
                ],
                "subtotal": 100,
                "total_tax": 18,
                "total_amount": 118
            }
            
            result = self.validator.validate(invoice)
            
            assert result.is_valid == False, f"Should fail for GSTIN: {bad_gstin}"
            assert any("GSTIN" in err for err in result.errors), \
                   f"Should have GSTIN error for: {bad_gstin}"
    
    def test_empty_line_items_list(self):
        """Test invoice with empty line items"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [],  # Empty!
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("line item" in err.lower() for err in result.errors)
    
    def test_line_item_calculation_errors(self):
        """Test line items with wrong calculations"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {
                    "description": "Item",
                    "quantity": 5,
                    "rate": 100,
                    "amount": 999  # Should be 500!
                }
            ],
            "subtotal": 999,
            "total_tax": 0,
            "total_amount": 999
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("calculation" in err.lower() for err in result.errors)
    
    def test_amount_mismatch_subtotal_tax_total(self):
        """Test when subtotal + tax ≠ total"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": 1, "rate": 100, "amount": 100}
            ],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 999  # Should be 118!
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("mismatch" in err.lower() for err in result.errors)
    
    def test_tax_components_mismatch(self):
        """Test when CGST + SGST + IGST ≠ total tax"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": 1, "rate": 100, "amount": 100}
            ],
            "subtotal": 100,
            "cgst_amount": 5,
            "sgst_amount": 5,
            "igst_amount": 0,
            "total_tax": 18,  # Should be 10!
            "total_amount": 118
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("tax" in err.lower() and "mismatch" in err.lower() 
                   for err in result.errors)
    
    def test_missing_line_item_fields(self):
        """Test line items missing required fields"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {
                    "description": "Item",
                    # Missing quantity, rate, amount!
                }
            ],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = self.validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("missing field" in err.lower() for err in result.errors)
    
    def test_safe_validation_with_none(self):
        """Test that safe validation handles None gracefully"""
        is_valid, errors = self.validator.validate_safe(None)
        
        assert is_valid == False
        assert len(errors) > 0
    
    def test_safe_validation_with_string(self):
        """Test that safe validation handles string gracefully"""
        is_valid, errors = self.validator.validate_safe("not a dict")
        
        assert is_valid == False
        assert len(errors) > 0
    
    def test_safe_validation_with_list(self):
        """Test that safe validation handles list gracefully"""
        is_valid, errors = self.validator.validate_safe([1, 2, 3])
        
        assert is_valid == False
        assert len(errors) > 0


class TestEdgeCaseValidation:
    """Test edge cases and boundary conditions"""
    
    def test_minimum_valid_invoice(self):
        """Test invoice with absolute minimum valid data"""
        invoice = {
            "invoice_number": "I",
            "invoice_date": "2024-01-01",
            "vendor": {"name": "V", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "B", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "I", "quantity": 1, "rate": 1, "amount": 1}
            ],
            "subtotal": 1,
            "total_tax": 0,
            "total_amount": 1
        }
        
        validator = InvoiceValidator()
        result = validator.validate(invoice)
        
        # Should be valid (minimal but complete)
        assert result.is_valid == True
    
    def test_unicode_in_descriptions(self):
        """Test Unicode characters in text fields"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "टेस्ट विक्रेता", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "परीक्षण खरीदार", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "वस्तु 商品", "quantity": 1, "rate": 100, "amount": 100}
            ],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118,
            "cgst_amount": 9,
            "sgst_amount": 9,
            "igst_amount": 0
        }
        
        validator = InvoiceValidator()
        result = validator.validate(invoice)
        
        # Should be valid (Unicode is fine in text fields)
        assert result.is_valid == True
    
    def test_floating_point_precision(self):
        """Test floating point calculation precision"""
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item", "quantity": 3, "rate": 33.33, "amount": 99.99}
            ],
            "subtotal": 99.99,
            "total_tax": 17.9982,  # 18% of 99.99
            "total_amount": 117.9882,
            "cgst_amount": 8.9991,
            "sgst_amount": 8.9991,
            "igst_amount": 0
        }
        
        validator = InvoiceValidator()
        result = validator.validate(invoice)
        
        # Should be valid (within rounding tolerance)
        assert result.is_valid == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
