from enum import Enum


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    SAVINGS = "SAVINGS"


class CategoryType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    SAVINGS = "SAVINGS"


class RiskTolerance(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class GoalType(str, Enum):
    EMERGENCY_FUND = "EMERGENCY_FUND"
    TRAVEL = "TRAVEL"
    LONG_TERM_WEALTH = "LONG_TERM_WEALTH"
    OTHER = "OTHER"


class AlertType(str, Enum):
    BUDGET = "BUDGET"
    GOAL = "GOAL"
    TRANSACTION = "TRANSACTION"
    SYSTEM = "SYSTEM"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"