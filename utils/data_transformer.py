"""
Data transformer to flatten nested invoice structure from test data
Converts vendor/buyer nested structure to flat seller/buyer fields
"""

from typing import Dict, Any
from datetime import datetime


def transform_invoice_data(invoice_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform nested invoice structure to flat structure expected by validators

    Input structure (from test_invoices.json):
        {
            "vendor": {"name": "...", "gstin": "...", "pan": "..."},
            "buyer": {"name": "...", "gstin": "..."},
            ...
        }

    Output structure (for validators):
        {
            "seller_name": "...",
            "seller_gstin": "...",
            "seller_state": "...",
            "buyer_name": "...",
            "buyer_gstin": "...",
            ...
        }
    """

    transformed = invoice_dict.copy()

    # Transform vendor -> seller
    if "vendor" in invoice_dict:
        vendor = invoice_dict["vendor"]
        transformed["seller_name"] = vendor.get("name", "")
        transformed["seller_gstin"] = vendor.get("gstin", "")
        transformed["seller_pan"] = vendor.get("pan", "")

        # Extract state from GSTIN (first 2 digits) or address
        seller_gstin = vendor.get("gstin", "")
        if len(seller_gstin) >= 2:
            state_code = seller_gstin[:2]
            transformed["seller_state"] = _get_state_name(state_code)
        else:
            transformed["seller_state"] = None

        # Handle non-resident vendors
        if "country" in vendor:
            transformed["seller_country"] = vendor["country"]
            transformed["seller_state"] = vendor["country"]

    # Transform buyer -> buyer (keep same name but flatten)
    if "buyer" in invoice_dict:
        buyer = invoice_dict["buyer"]
        transformed["buyer_name"] = buyer.get("name", "")
        transformed["buyer_gstin"] = buyer.get("gstin", "")

        # Extract state from GSTIN
        buyer_gstin = buyer.get("gstin", "")
        if len(buyer_gstin) >= 2:
            state_code = buyer_gstin[:2]
            transformed["buyer_state"] = _get_state_name(state_code)
        else:
            transformed["buyer_state"] = None

        # Handle non-resident buyers
        if "country" in buyer:
            transformed["buyer_country"] = buyer["country"]

    # Add missing fields with defaults
    transformed.setdefault("place_of_supply", None)
    transformed.setdefault("reverse_charge", False)
    transformed.setdefault("qr_code_present", transformed.get("qr_code_present", False))
    transformed.setdefault("tds_applicable", False)
    transformed.setdefault("tds_section", None)
    transformed.setdefault("tds_rate", None)
    transformed.setdefault("tds_amount", None)
    transformed.setdefault("extraction_confidence", 1.0)
    transformed.setdefault("format_type", "json")
    transformed.setdefault("total_tax", 0)

    # Calculate total_tax if not present
    if "total_tax" not in invoice_dict or invoice_dict["total_tax"] is None:
        cgst = transformed.get("cgst_amount", 0) or 0
        sgst = transformed.get("sgst_amount", 0) or 0
        igst = transformed.get("igst_amount", 0) or 0
        transformed["total_tax"] = cgst + sgst + igst

    # Handle line items - add tax_rate if not present
    if "line_items" in transformed:
        line_items = []
        for item in transformed["line_items"]:
            new_item = item.copy()

            # Calculate tax_rate if not present
            if "tax_rate" not in new_item:
                # Determine tax rate from invoice level
                if transformed.get("igst_rate", 0) > 0:
                    new_item["tax_rate"] = transformed.get("igst_rate", 0)
                else:
                    cgst_rate = transformed.get("cgst_rate", 0) or 0
                    sgst_rate = transformed.get("sgst_rate", 0) or 0
                    new_item["tax_rate"] = cgst_rate + sgst_rate

            line_items.append(new_item)

        transformed["line_items"] = line_items

    return transformed


def _get_state_name(state_code: str) -> str:
    """Get state name from state code"""

    state_mapping = {
        "01": "Jammu and Kashmir",
        "02": "Himachal Pradesh",
        "03": "Punjab",
        "04": "Chandigarh",
        "05": "Uttarakhand",
        "06": "Haryana",
        "07": "Delhi",
        "08": "Rajasthan",
        "09": "Uttar Pradesh",
        "10": "Bihar",
        "11": "Sikkim",
        "12": "Arunachal Pradesh",
        "13": "Nagaland",
        "14": "Manipur",
        "15": "Mizoram",
        "16": "Tripura",
        "17": "Meghalaya",
        "18": "Assam",
        "19": "West Bengal",
        "20": "Jharkhand",
        "21": "Odisha",
        "22": "Chhattisgarh",
        "23": "Madhya Pradesh",
        "24": "Gujarat",
        "26": "Dadra and Nagar Haveli and Daman and Diu",
        "27": "Maharashtra",
        "29": "Karnataka",
        "30": "Goa",
        "31": "Lakshadweep",
        "32": "Kerala",
        "33": "Tamil Nadu",
        "34": "Puducherry",
        "35": "Andaman and Nicobar Islands",
        "36": "Telangana",
        "37": "Andhra Pradesh",
        "38": "Ladakh",
    }

    return state_mapping.get(state_code, f"State-{state_code}")