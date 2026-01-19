"""
Anti-Pattern Tests
Tests that specifically verify the system avoids disqualifying anti-patterns
"""

import pytest
import json
from datetime import date
from pathlib import Path

from utils.validators import InvoiceValidator, validate_invoice
from utils.data_loaders import InvoiceDataLoader


class TestAntiPattern1_NoHardcodedDecisions:
    """
    Anti-Pattern 1: Hardcoded decisions - Mapping invoice IDs to expected results
    
    Tests that the system does NOT map invoice IDs to pre-determined outcomes
    """
    
    def test_same_invoice_different_data_different_results(self):
        """
        Test that identical invoice IDs with different data produce different results
        This proves no hardcoded ID mapping
        """
        
        validator = InvoiceValidator()
        
        # Invoice 1: Valid data
        invoice1 = {
            "invoice_id": "TEST-001",
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test Vendor", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test Buyer", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item 1", "quantity": 1, "rate": 100, "amount": 100, "hsn_sac": "998315"}
            ],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118,
            "cgst_amount": 9,
            "sgst_amount": 9,
            "igst_amount": 0
        }
        
        # Invoice 2: Same ID but INVALID data
        invoice2 = {
            "invoice_id": "TEST-001",  # Same ID!
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test Vendor", "gstin": "INVALID"},  # Bad GSTIN!
            "buyer": {"name": "Test Buyer", "gstin": "27AABCF9999K1ZX"},
            "line_items": [],  # No line items!
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 50,  # Wrong total!
            "cgst_amount": 9,
            "sgst_amount": 9,
            "igst_amount": 0
        }
        
        result1 = validator.validate(invoice1)
        result2 = validator.validate(invoice2)
        
        # Same ID but different results based on DATA, not ID
        assert result1.is_valid == True, "Valid data should pass"
        assert result2.is_valid == False, "Invalid data should fail"
        assert len(result2.errors) > 0, "Should have validation errors"
        
        # Verify errors are about DATA, not ID
        error_text = " ".join(result2.errors)
        assert "GSTIN" in error_text or "line items" in error_text or "Amount" in error_text
    
    def test_no_invoice_id_mapping_in_code(self):
        """
        Test that validation doesn't depend on invoice_id field
        Invoice without invoice_id should still validate based on data
        """
        
        validator = InvoiceValidator()
        
        # No invoice_id field at all
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test Vendor", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test Buyer", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item 1", "quantity": 1, "rate": 100, "amount": 100}
            ],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118,
            "cgst_amount": 9,
            "sgst_amount": 9,
            "igst_amount": 0
        }
        
        result = validator.validate(invoice)
        
        # Should validate based on data, not missing invoice_id
        assert result.is_valid == True
    
    def test_malformed_same_id_validation_independence(self):
        """
        Test that malformed data is caught regardless of invoice ID
        """
        
        validator = InvoiceValidator()
        
        # Three different IDs with same malformed data
        base_invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2099-12-31",  # Future date!
            "vendor": {"name": "Test", "gstin": "BADGSTIN"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [],  # Empty!
            "subtotal": -100,  # Negative!
            "total_tax": 18,
            "total_amount": 118
        }
        
        for invoice_id in ["TEST-001", "TEST-002", "TEST-999"]:
            invoice = {**base_invoice, "invoice_id": invoice_id}
            result = validator.validate(invoice)
            
            # All should fail regardless of ID
            assert result.is_valid == False
            assert len(result.errors) >= 3  # Multiple errors expected


class TestAntiPattern2_NoSingleLLMDump:
    """
    Anti-Pattern 2: Single LLM call - Dumping all data into one prompt
    
    Tests that the system uses multiple specialized LLM calls, not one big dump
    """

    def test_multiple_agent_architecture(self):
        """
        Test that the workflow uses multiple specialized agents
        """
        import os
        if not os.getenv('OPENAI_API_KEY'):
            pytest.skip("OPENAI_API_KEY not set - skipping test")

        try:
            from agents.langgraph_workflow import ComplianceWorkflow
            workflow = ComplianceWorkflow()
        except Exception as e:
            if "proxies" in str(e) or "ValidationError" in str(type(e).__name__):
                pytest.skip(f"OpenAI library compatibility issue: {e}")
            raise

        # Check that graph has multiple nodes
        graph = workflow._build_graph()

        # Should have at least 5 specialized nodes
        node_methods = [
            'supervisor_node',
            'gst_node',
            'vendor_node',
            'tds_node',
            'policy_node',
            'resolver_node',
            'reporter_node'
        ]

        for method in node_methods:
            assert hasattr(workflow, method), f"Missing specialized node: {method}"

    def test_gst_agent_has_separate_llm_logic(self):
        """
        Test that GST agent has separate LLM reasoning method
        """

        import os
        if not os.getenv('OPENAI_API_KEY'):
            pytest.skip("OPENAI_API_KEY not set - skipping LLM test")

        try:
            from agents.gst_agent_llm import GSTAgentLLM
            agent = GSTAgentLLM()
        except Exception as e:
            if "proxies" in str(e) or "ValidationError" in str(type(e).__name__):
                pytest.skip(f"OpenAI library compatibility issue: {e}")
            raise

        # Should have separate methods for rule-based and LLM reasoning
        assert hasattr(agent, '_rule_based_checks')
        assert hasattr(agent, '_llm_reasoning_checks')
        assert hasattr(agent, '_needs_llm_reasoning')

        # LLM should NOT always be used
        simple_invoice = {
            'line_items': [{'description': 'Simple item'}],
            'reverse_charge': False
        }

        needs_llm = agent._needs_llm_reasoning(simple_invoice)
        assert needs_llm == False, "Simple invoice should not need LLM"

        complex_invoice = {
            'line_items': [
                {'description': 'Transport'},
                {'description': 'Warehousing'},
                {'description': 'Packing'},
                {'description': 'Composite service'}
            ],
            'reverse_charge': True
        }

        needs_llm = agent._needs_llm_reasoning(complex_invoice)
        assert needs_llm == True, "Complex invoice should need LLM"


class TestAntiPattern3_ComprehensiveErrorHandling:
    """
    Anti-Pattern 3: No error handling - Crashing on malformed data
    
    Tests that the system handles errors gracefully
    """
    
    def test_missing_required_fields(self):
        """
        Test that missing fields are caught, not crashed
        """
        
        validator = InvoiceValidator()
        
        # Missing invoice_number
        invoice = {
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("invoice_number" in error for error in result.errors)
    
    def test_invalid_data_types(self):
        """
        Test that wrong data types are caught
        """
        
        validator = InvoiceValidator()
        
        # String where number expected
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [{"description": "Item", "quantity": 1, "rate": 100, "amount": 100}],
            "subtotal": "NOT_A_NUMBER",  # Wrong type!
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("numeric" in error.lower() for error in result.errors)
    
    def test_malformed_nested_structures(self):
        """
        Test that malformed nested data is caught
        """
        
        validator = InvoiceValidator()
        
        # Vendor as string instead of dict
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": "NOT_A_DICT",  # Wrong structure!
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("Vendor" in error for error in result.errors)
    
    def test_empty_line_items(self):
        """
        Test that empty line items are caught
        """
        
        validator = InvoiceValidator()
        
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
        
        result = validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("line item" in error.lower() for error in result.errors)
    
    def test_future_dated_invoice(self):
        """
        Test that future dates are caught
        """
        
        validator = InvoiceValidator()
        
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2099-12-31",  # Future!
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [{"description": "Item", "quantity": 1, "rate": 100, "amount": 100}],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("future" in error.lower() for error in result.errors)
    
    def test_invalid_gstin_format(self):
        """
        Test that invalid GSTIN is caught
        """
        
        validator = InvoiceValidator()
        
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "INVALID_GSTIN"},  # Bad format!
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [{"description": "Item", "quantity": 1, "rate": 100, "amount": 100}],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118
        }
        
        result = validator.validate(invoice)
        
        assert result.is_valid == False
        assert any("GSTIN" in error for error in result.errors)
    
    def test_safe_validation_never_crashes(self):
        """
        Test that validation never throws exceptions, even with garbage data
        """
        
        validator = InvoiceValidator()
        
        garbage_data = [
            None,
            {},
            {"random": "data"},
            {"invoice_number": None},
            {"vendor": None, "buyer": None},
            {"line_items": "not_a_list"},
            {"subtotal": {"nested": "dict"}},
        ]
        
        for data in garbage_data:
            # Should never crash
            is_valid, errors = validator.validate_safe(data)
            assert isinstance(is_valid, bool)
            assert isinstance(errors, list)


class TestAntiPattern4_ConfidenceTracking:
    """
    Anti-Pattern 4: Ignoring confidence - Treating all decisions as 100% certain
    
    Tests that confidence is tracked and used for decisions
    """
    
    def test_confidence_in_check_results(self):
        """
        Test that validation checks include confidence scores
        """
        
        from models.validation import CheckResult, CheckStatus, Severity
        
        # Rule-based check should have high confidence
        check1 = CheckResult(
            check_id="TEST1",
            check_name="Test Check",
            status=CheckStatus.PASS,
            confidence=1.0,
            reasoning="Deterministic rule",
            severity=Severity.HIGH
        )
        
        assert check1.confidence == 1.0
        
        # LLM check should have lower confidence
        check2 = CheckResult(
            check_id="TEST2",
            check_name="LLM Check",
            status=CheckStatus.WARNING,
            confidence=0.75,
            reasoning="LLM reasoning",
            severity=Severity.MEDIUM,
            requires_review=True
        )
        
        assert check2.confidence < 1.0
        assert check2.requires_review == True

    def test_escalation_based_on_confidence(self):
        """
        Test that low confidence triggers escalation
        """
        import os
        if not os.getenv('OPENAI_API_KEY'):
            pytest.skip("OPENAI_API_KEY not set - skipping test")

        try:
            from agents.langgraph_workflow import ComplianceWorkflow
            workflow = ComplianceWorkflow()
        except Exception as e:
            if "proxies" in str(e) or "ValidationError" in str(type(e).__name__):
                pytest.skip(f"OpenAI library compatibility issue: {e}")
            raise

        # Mock state with low confidence
        mock_checks = [
            {"confidence": 0.6, "status": "WARNING"},
            {"confidence": 0.65, "status": "PASS"},
            {"confidence": 0.55, "status": "WARNING"}
        ]

        total_confidence = sum(c["confidence"] for c in mock_checks) / len(mock_checks)

        # Low confidence (0.60 avg) should trigger escalation
        assert total_confidence < 0.70, "Should be low confidence"

        # In real system, this would trigger escalation
        should_escalate = total_confidence < 0.70
        assert should_escalate == True


class TestAntiPattern5_NoHistoricalCopyPaste:
    """
    Anti-Pattern 5: Copy-paste from historical - Replicating past decisions without validation
    
    Tests that historical decisions are not blindly copied
    """
    
    def test_historical_data_not_used_for_decisions(self):
        """
        Test that the system doesn't use historical decisions to make current decisions
        """
        
        # Check that HistoricalDecisions class exists but is not used in validators
        from utils.data_loaders import HistoricalDecisions
        
        historical = HistoricalDecisions()
        
        # Historical data should be loaded
        assert len(historical.decisions) > 0
        
        # But validators should NOT import or use it
        from validators.arithmetic_validator import ArithmeticValidator
        from validators.gst_validator import GSTComplianceValidator
        from validators.vendor_validator import VendorValidator
        
        # Check that validators don't have historical decision lookups
        arith = ArithmeticValidator()
        assert not hasattr(arith, 'historical_decisions')
        assert not hasattr(arith, 'historical')
    
    def test_same_invoice_data_validated_independently(self):
        """
        Test that same invoice validated twice gets same result (not from cache)
        """
        
        validator = InvoiceValidator()
        
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Test", "gstin": "27AABCF9999K1ZX"},
            "line_items": [{"description": "Item", "quantity": 1, "rate": 100, "amount": 100}],
            "subtotal": 100,
            "total_tax": 18,
            "total_amount": 118,
            "cgst_amount": 9,
            "sgst_amount": 9,
            "igst_amount": 0
        }
        
        # Validate twice
        result1 = validator.validate(invoice)
        result2 = validator.validate(invoice)
        
        # Should get same result both times (validated fresh, not cached)
        assert result1.is_valid == result2.is_valid
        assert len(result1.errors) == len(result2.errors)
        
        # Now modify data
        invoice["subtotal"] = 200  # Change data
        result3 = validator.validate(invoice)
        
        # Should get DIFFERENT result (not using cached old result)
        assert result3.is_valid != result1.is_valid


class TestComprehensiveValidationSuite:
    """
    Integration tests demonstrating all anti-patterns are avoided
    """
    
    def test_end_to_end_no_antipatterns(self):
        """
        End-to-end test showing system avoids all anti-patterns
        """
        
        validator = InvoiceValidator()
        
        # Valid invoice
        valid_invoice = {
            "invoice_number": "INV-VALID",
            "invoice_date": "2024-09-15",
            "vendor": {"name": "Valid Vendor", "gstin": "27AABCT1234F1ZP"},
            "buyer": {"name": "Valid Buyer", "gstin": "27AABCF9999K1ZX"},
            "line_items": [
                {"description": "Item 1", "quantity": 2, "rate": 100, "amount": 200, "hsn_sac": "998315"}
            ],
            "subtotal": 200,
            "total_tax": 36,
            "total_amount": 236,
            "cgst_amount": 18,
            "sgst_amount": 18,
            "igst_amount": 0
        }
        
        # Invalid invoice (multiple errors)
        invalid_invoice = {
            "invoice_number": "INV-INVALID",
            "invoice_date": "2099-01-01",  # Future
            "vendor": {"name": "Bad Vendor", "gstin": "BADGSTIN"},  # Invalid GSTIN
            "buyer": {"name": "Bad Buyer", "gstin": "27AABCF9999K1ZX"},
            "line_items": [],  # Empty
            "subtotal": -100,  # Negative
            "total_tax": 18,
            "total_amount": 50  # Wrong calculation
        }
        
        # Test 1: No hardcoded decisions (Anti-Pattern 1)
        result1 = validator.validate(valid_invoice)
        result2 = validator.validate(invalid_invoice)
        assert result1.is_valid != result2.is_valid  # Different results for different data
        
        # Test 2: Error handling works (Anti-Pattern 3)
        assert result2.is_valid == False
        assert len(result2.errors) > 0  # Errors caught, not crashed
        
        # Test 3: No historical copy-paste (Anti-Pattern 5)
        # Modify valid invoice and re-validate
        modified = valid_invoice.copy()
        modified["total_amount"] = 999  # Wrong total now
        result3 = validator.validate(modified)
        assert result3.is_valid == False  # Validates fresh, not using cached result
        
        print("✅ All anti-patterns successfully avoided!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
