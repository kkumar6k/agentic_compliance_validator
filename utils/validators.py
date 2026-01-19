"""
Validation Layer for Invoice Data
Comprehensive validation to catch malformed data before processing
"""

from typing import Dict, List, Tuple, Optional
from datetime import date, datetime
import re
from pydantic import BaseModel, ValidationError


class ValidationResult:
    """Result of validation check"""
    
    def __init__(self, is_valid: bool, errors: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
    
    def __bool__(self):
        return self.is_valid
    
    def add_error(self, error: str):
        self.errors.append(error)
        self.is_valid = False


class InvoiceValidator:
    """
    Comprehensive invoice data validator
    Prevents malformed data from reaching the validation pipeline
    """
    
    def __init__(self):
        self.gstin_pattern = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9]{1}[Z]{1}[0-9A-Z]{1}$')
        self.required_fields = [
            'invoice_number',
            'invoice_date',
            'vendor',
            'buyer',
            'line_items',
            'subtotal',
            'total_tax',
            'total_amount'
        ]
    
    def validate(self, invoice_data: Dict) -> ValidationResult:
        """
        Comprehensive validation of invoice data
        
        Args:
            invoice_data: Invoice dictionary to validate
            
        Returns:
            ValidationResult with is_valid flag and error list
        """
        result = ValidationResult(is_valid=True)
        
        # 1. Check required fields
        self._validate_required_fields(invoice_data, result)
        if not result:
            return result  # Stop if missing required fields
        
        # 2. Validate structure
        self._validate_structure(invoice_data, result)
        
        # 3. Validate data types
        self._validate_data_types(invoice_data, result)
        
        # 4. Validate business rules
        self._validate_business_rules(invoice_data, result)
        
        # 5. Validate GSTINs
        self._validate_gstins(invoice_data, result)
        
        # 6. Validate line items
        self._validate_line_items(invoice_data, result)
        
        # 7. Validate amounts
        self._validate_amounts(invoice_data, result)
        
        return result
    
    def _validate_required_fields(self, data: Dict, result: ValidationResult):
        """Check all required fields are present"""
        for field in self.required_fields:
            if field not in data:
                result.add_error(f"Missing required field: {field}")
    
    def _validate_structure(self, data: Dict, result: ValidationResult):
        """Validate nested structure"""
        
        # Vendor structure
        if 'vendor' in data:
            vendor = data['vendor']
            if not isinstance(vendor, dict):
                result.add_error("Vendor must be a dictionary")
            elif 'name' not in vendor or 'gstin' not in vendor:
                result.add_error("Vendor missing required fields (name, gstin)")
        
        # Buyer structure
        if 'buyer' in data:
            buyer = data['buyer']
            if not isinstance(buyer, dict):
                result.add_error("Buyer must be a dictionary")
            elif 'name' not in buyer or 'gstin' not in buyer:
                result.add_error("Buyer missing required fields (name, gstin)")
        
        # Line items structure
        if 'line_items' in data:
            if not isinstance(data['line_items'], list):
                result.add_error("Line items must be a list")
            elif len(data['line_items']) == 0:
                result.add_error("Invoice must have at least one line item")
    
    def _validate_data_types(self, data: Dict, result: ValidationResult):
        """Validate data types"""
        
        # String fields
        string_fields = ['invoice_number', 'invoice_date']
        for field in string_fields:
            if field in data and not isinstance(data[field], str):
                result.add_error(f"{field} must be a string")
        
        # Numeric fields
        numeric_fields = ['subtotal', 'total_tax', 'total_amount', 
                         'cgst_amount', 'sgst_amount', 'igst_amount']
        for field in numeric_fields:
            if field in data and data[field] is not None:
                try:
                    float(data[field])
                except (TypeError, ValueError):
                    result.add_error(f"{field} must be numeric")
    
    def _validate_business_rules(self, data: Dict, result: ValidationResult):
        """Validate business logic rules"""
        
        # Invoice date validation
        if 'invoice_date' in data:
            try:
                invoice_date = date.fromisoformat(data['invoice_date'])
                
                # Check not in future
                if invoice_date > date.today():
                    result.add_error(f"Invoice date cannot be in future: {invoice_date}")
                
                # Check not too old (10 years)
                if (date.today() - invoice_date).days > 3650:
                    result.add_error(f"Invoice date too old: {invoice_date}")
                    
            except (ValueError, TypeError) as e:
                result.add_error(f"Invalid invoice date format: {data['invoice_date']} - {str(e)}")
        
        # Amount validations
        if 'total_amount' in data:
            try:
                total = float(data['total_amount'])
                if total <= 0:
                    result.add_error(f"Total amount must be positive: {total}")
                if total > 1_000_000_000:  # 100 crore limit
                    result.add_error(f"Total amount unreasonably high: {total}")
            except (TypeError, ValueError):
                pass  # Already caught in data type validation
    
    def _validate_gstins(self, data: Dict, result: ValidationResult):
        """Validate GSTIN formats"""
        
        # Seller GSTIN
        if 'vendor' in data and isinstance(data['vendor'], dict):
            seller_gstin = data['vendor'].get('gstin', '')
            if seller_gstin and not self.gstin_pattern.match(seller_gstin):
                result.add_error(f"Invalid seller GSTIN format: {seller_gstin}")
        
        # Buyer GSTIN
        if 'buyer' in data and isinstance(data['buyer'], dict):
            buyer_gstin = data['buyer'].get('gstin', '')
            if buyer_gstin and not self.gstin_pattern.match(buyer_gstin):
                result.add_error(f"Invalid buyer GSTIN format: {buyer_gstin}")
    
    def _validate_line_items(self, data: Dict, result: ValidationResult):
        """Validate line items"""
        
        if 'line_items' not in data or not isinstance(data['line_items'], list):
            return
        
        for i, item in enumerate(data['line_items'], 1):
            if not isinstance(item, dict):
                result.add_error(f"Line item {i} must be a dictionary")
                continue
            
            # Required line item fields
            required = ['description', 'quantity', 'rate', 'amount']
            for field in required:
                if field not in item:
                    result.add_error(f"Line item {i} missing field: {field}")
            
            # Validate numeric fields
            if 'quantity' in item:
                try:
                    qty = float(item['quantity'])
                    if qty <= 0:
                        result.add_error(f"Line item {i} quantity must be positive")
                except (TypeError, ValueError):
                    result.add_error(f"Line item {i} quantity must be numeric")
            
            if 'rate' in item:
                try:
                    rate = float(item['rate'])
                    if rate < 0:
                        result.add_error(f"Line item {i} rate cannot be negative")
                except (TypeError, ValueError):
                    result.add_error(f"Line item {i} rate must be numeric")
            
            if 'amount' in item:
                try:
                    amount = float(item['amount'])
                    if amount < 0:
                        result.add_error(f"Line item {i} amount cannot be negative")
                except (TypeError, ValueError):
                    result.add_error(f"Line item {i} amount must be numeric")
            
            # Validate calculation
            if all(k in item for k in ['quantity', 'rate', 'amount']):
                try:
                    expected = float(item['quantity']) * float(item['rate'])
                    actual = float(item['amount'])
                    if abs(expected - actual) > 0.01:
                        result.add_error(
                            f"Line item {i} calculation error: "
                            f"{item['quantity']} × {item['rate']} ≠ {item['amount']}"
                        )
                except (TypeError, ValueError):
                    pass  # Already caught above
    
    def _validate_amounts(self, data: Dict, result: ValidationResult):
        """Validate amount consistency"""
        
        try:
            subtotal = float(data.get('subtotal', 0))
            total_tax = float(data.get('total_tax', 0))
            total_amount = float(data.get('total_amount', 0))
            
            # Check total = subtotal + tax
            expected_total = subtotal + total_tax
            if abs(expected_total - total_amount) > 0.01:
                result.add_error(
                    f"Amount mismatch: subtotal ({subtotal}) + tax ({total_tax}) "
                    f"≠ total ({total_amount})"
                )
            
            # Check tax components
            cgst = float(data.get('cgst_amount', 0))
            sgst = float(data.get('sgst_amount', 0))
            igst = float(data.get('igst_amount', 0))
            cess = float(data.get('cess', 0))
            
            expected_tax = cgst + sgst + igst + cess
            if abs(expected_tax - total_tax) > 0.01:
                result.add_error(
                    f"Tax mismatch: CGST + SGST + IGST + Cess "
                    f"({expected_tax}) ≠ Total Tax ({total_tax})"
                )
            
        except (TypeError, ValueError, KeyError):
            pass  # Data type errors already caught
    
    def validate_safe(self, invoice_data: Dict) -> Tuple[bool, List[str]]:
        """
        Safe validation that never throws exceptions
        
        Returns:
            (is_valid, error_list)
        """
        try:
            result = self.validate(invoice_data)
            return result.is_valid, result.errors
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]


class PydanticValidator:
    """Validates using Pydantic models (fallback validation)"""
    
    @staticmethod
    def validate_with_model(invoice_data: Dict, model_class: BaseModel) -> Tuple[bool, Optional[str]]:
        """
        Validate data against Pydantic model
        
        Returns:
            (is_valid, error_message)
        """
        try:
            model_class(**invoice_data)
            return True, None
        except ValidationError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected validation error: {str(e)}"


# Convenience function
def validate_invoice(invoice_data: Dict) -> ValidationResult:
    """
    Quick validation function
    
    Usage:
        result = validate_invoice(invoice_json)
        if result:
            # Process invoice
        else:
            print(f"Validation errors: {result.errors}")
    """
    validator = InvoiceValidator()
    return validator.validate(invoice_data)
