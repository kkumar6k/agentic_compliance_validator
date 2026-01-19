"""
Validation result models
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CheckResult(BaseModel):
    """Result of a single validation check"""
    check_id: str
    check_name: str
    status: CheckStatus
    confidence: float
    reasoning: str
    severity: Severity = Severity.MEDIUM
    requires_review: bool = False
    rag_context: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class CategoryResult(BaseModel):
    """Result of category validation"""
    category: str
    category_name: str
    checks: List[CheckResult]
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    average_confidence: float = 0.0
    
    def __init__(self, **data):
        super().__init__(**data)
        self._calculate_stats()
    
    def _calculate_stats(self):
        """Calculate category statistics"""
        if not self.checks:
            return
            
        self.passed_count = len([c for c in self.checks if c.status == CheckStatus.PASS])
        self.failed_count = len([c for c in self.checks if c.status == CheckStatus.FAIL])
        self.warning_count = len([c for c in self.checks if c.status == CheckStatus.WARNING])
        
        if self.checks:
            self.average_confidence = sum(c.confidence for c in self.checks) / len(self.checks)


class ValidationResult(BaseModel):
    """Complete validation result"""
    invoice_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    category_results: Dict[str, CategoryResult] = {}
    passed_checks: int = 0
    failed_checks: int = 0
    warnings: int = 0
    average_confidence: float = 0.0
    requires_review: bool = False
    overall_status: str = "PENDING"
    
    def has_conflicts(self) -> bool:
        """Check if validation has conflicts"""
        for category in self.category_results.values():
            for check in category.checks:
                if check.requires_review:
                    return True
        return False
    
    def get_critical_issues(self) -> List[CheckResult]:
        """Get all critical failed checks"""
        issues = []
        for category in self.category_results.values():
            for check in category.checks:
                if check.status == CheckStatus.FAIL and \
                   check.severity in [Severity.HIGH, Severity.CRITICAL]:
                    issues.append(check)
        return issues
