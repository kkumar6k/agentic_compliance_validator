"""
Data loaders for all challenge data files
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from datetime import date, datetime
import yaml


class InvoiceDataLoader:
    """Load and manage test invoices"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.invoices = self._load_invoices()
    
    def _load_invoices(self) -> List[Dict]:
        """Load all test invoices"""
        invoice_file = self.data_dir / "test_invoices.json"
        
        with open(invoice_file) as f:
            return json.load(f)
    
    def get_invoice(self, invoice_id: str) -> Dict:
        """Get specific invoice by ID"""
        for inv in self.invoices:
            if inv['invoice_id'] == invoice_id:
                return inv
        raise ValueError(f"Invoice {invoice_id} not found")
    
    def get_by_category(self, category: str) -> List[Dict]:
        """Get invoices by test category"""
        return [
            inv for inv in self.invoices 
            if inv.get('_test_category') == category
        ]
    
    def get_by_complexity(self, complexity: str) -> List[Dict]:
        """Get invoices by complexity level"""
        return [
            inv for inv in self.invoices 
            if inv.get('_complexity') == complexity
        ]


class VendorRegistry:
    """Manage vendor data"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.vendors = self._load_vendors()
        self.gstin_index = self._build_gstin_index()
        self.pan_index = self._build_pan_index()
    
    def _load_vendors(self) -> List[Dict]:
        """Load vendor registry"""
        vendor_file = self.data_dir / "vendor_registry.json"
        
        with open(vendor_file) as f:
            data = json.load(f)
            return data['vendors']
    
    def _build_gstin_index(self) -> Dict:
        """Build GSTIN lookup index"""
        return {v['gstin']: v for v in self.vendors if v.get('gstin')}
    
    def _build_pan_index(self) -> Dict:
        """Build PAN lookup index"""
        pan_index = {}
        for v in self.vendors:
            pan = v.get('pan')
            if pan:
                if pan not in pan_index:
                    pan_index[pan] = []
                pan_index[pan].append(v)
        return pan_index
    
    def get_by_gstin(self, gstin: str) -> Dict:
        """Get vendor by GSTIN"""
        vendor = self.gstin_index.get(gstin)
        if not vendor:
            raise ValueError(f"Vendor with GSTIN {gstin} not found")
        return vendor
    
    def is_related_party(self, gstin: str) -> bool:
        """Check if vendor is related party"""
        try:
            vendor = self.get_by_gstin(gstin)
            pan = vendor.get('pan')
            if pan:
                return len(self.pan_index.get(pan, [])) > 1
        except ValueError:
            pass
        return False


class GSTRateSchedule:
    """Manage GST rates with temporal validity"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.rates_df = self._load_rates()
    
    def _load_rates(self) -> pd.DataFrame:
        """Load GST rates schedule"""
        rates_file = self.data_dir / "gst_rates_schedule.csv"
        
        df = pd.read_csv(rates_file)
        df['effective_from'] = pd.to_datetime(df['effective_from'])
        df['effective_to'] = pd.to_datetime(df['effective_to'])
        
        return df
    
    def get_rate(self, hsn_sac: str, invoice_date: date) -> Dict:
        """Get applicable GST rate for date"""
        
        matches = self.rates_df[self.rates_df['hsn_sac_code'] == hsn_sac]
        
        if matches.empty:
            raise ValueError(f"HSN/SAC {hsn_sac} not found")
        
        invoice_dt = pd.Timestamp(invoice_date)
        
        applicable = matches[
            (matches['effective_from'] <= invoice_dt) &
            ((matches['effective_to'].isna()) | (matches['effective_to'] >= invoice_dt))
        ]
        
        if applicable.empty:
            historical = matches[matches['effective_from'] <= invoice_dt]
            if not historical.empty:
                applicable = historical.sort_values('effective_from', ascending=False).head(1)
            else:
                raise ValueError(f"No rate found for {hsn_sac} on {invoice_date}")
        
        rate_row = applicable.iloc[0]
        
        return {
            'hsn_sac': hsn_sac,
            'description': rate_row['description'],
            'cgst': rate_row['rate_cgst'],
            'sgst': rate_row['rate_sgst'],
            'igst': rate_row['rate_igst'],
            'effective_from': rate_row['effective_from'].date()
        }


class HSNSACMaster:
    """Manage HSN/SAC codes"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.codes = self._load_codes()
    
    def _load_codes(self) -> Dict:
        """Load HSN/SAC codes"""
        codes_file = self.data_dir / "hsn_sac_codes.json"
        
        with open(codes_file) as f:
            return json.load(f)
    
    def get_code(self, code: str) -> Dict:
        """Get HSN/SAC code details"""
        hsn = self.codes.get('hsn_codes', {}).get(code)
        if hsn:
            return {**hsn, 'type': 'HSN'}
        
        sac = self.codes.get('sac_codes', {}).get(code)
        if sac:
            return {**sac, 'type': 'SAC'}
        
        raise ValueError(f"Code {code} not found")


class TDSSectionRules:
    """Manage TDS section rules"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.sections = self._load_sections()
    
    def _load_sections(self) -> Dict:
        """Load TDS sections"""
        sections_file = self.data_dir / "tds_sections.json"
        
        with open(sections_file) as f:
            data = json.load(f)
            return {s['section']: s for s in data['tds_sections']}
    
    def get_section(self, section: str) -> Optional[Dict]:
        """Get section details"""
        return self.sections.get(section)
    
    def get_rate(self, section: str, vendor_type: str, has_pan: bool = True) -> float:
        """Get applicable TDS rate"""
        section_data = self.get_section(section)
        
        if not section_data:
            return 0.0
        
        if not has_pan:
            return section_data.get('rate_no_pan', 20.0)
        
        if section == '194C':
            return section_data.get('rate_company', 2.0)
        elif section == '194J':
            return section_data.get('rate_technical', 2.0)
        elif section == '194H':
            return section_data.get('rate', 5.0)
        
        return section_data.get('rate', 0.0)


class CompanyPolicy:
    """Manage company policy rules"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.policy = self._load_policy()
    
    def _load_policy(self) -> Dict:
        """Load company policy"""
        policy_file = self.data_dir / "company_policy.yaml"
        
        with open(policy_file) as f:
            return yaml.safe_load(f)
    
    def get_approval_level(self, amount: float, vendor_gstin: str = None, 
                          is_first_time: bool = False, is_retrospective: bool = False) -> Dict:
        """Determine required approval level based on amount and risk factors"""
        
        levels = self.policy['approval_matrix']['levels']
        
        # Base approval level by amount
        base_level = None
        for level in levels:
            max_amount = level.get('max_amount')
            if max_amount is None or amount <= max_amount:
                base_level = level
                break
        
        if not base_level:
            base_level = levels[-1]
        
        # Increase approval level for risk factors
        approval_level = base_level['level']
        
        # First-time vendor or retrospective invoice requires +1 level
        if is_first_time or is_retrospective:
            approval_level = min(approval_level + 1, len(levels))
            
            # Find the higher level
            for level in levels:
                if level['level'] == approval_level:
                    return {
                        'level': level['level'],
                        'name': level['name'],
                        'approvers': level['approvers']
                    }
        
        return {
            'level': base_level['level'],
            'name': base_level['name'],
            'approvers': base_level['approvers']
        }


class HistoricalDecisions:
    """Load historical decisions (for future RAG/learning, not for copying decisions)"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.decisions = self._load_decisions()

    def _load_decisions(self) -> List[Dict]:
        """Load historical decision data"""
        decisions_file = self.data_dir / "historical_decisions.jsonl"

        decisions = []
        try:
            with open(decisions_file) as f:
                for line in f:
                    if line.strip():
                        decisions.append(json.loads(line))
        except FileNotFoundError:
            pass

        return decisions

    def get_by_invoice(self, invoice_id: str) -> Optional[Dict]:
        """Get historical decision for specific invoice"""
        for decision in self.decisions:
            if decision.get('invoice_id') == invoice_id:
                return decision
        return None
