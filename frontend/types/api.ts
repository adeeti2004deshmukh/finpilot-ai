export type Money = string | number;
export type TransactionKind = "INCOME" | "EXPENSE" | "SAVINGS";
export type RiskTolerance = "LOW" | "MODERATE" | "HIGH";
export type GoalKind = "EMERGENCY_FUND" | "TRAVEL" | "LONG_TERM_WEALTH" | "OTHER";

export interface User {
  id: number;
  name: string;
  email: string;
  age: number | null;
}

export interface FinancialProfile {
  id: number;
  user_id: number;
  monthly_income: Money;
  other_income: Money;
  typical_essential_expenses: Money;
  current_savings: Money;
  emergency_savings: Money;
  monthly_debt_payment: Money;
  total_debt: Money;
  dependents: number;
  risk_tolerance: RiskTolerance;
  emergency_fund_target_months: number;
  created_at: string;
  updated_at: string;
}

export interface Category {
  id: number;
  name: string;
  type: TransactionKind;
  is_essential: boolean;
  created_at: string;
}

export interface CategoryAmount {
  category_id: number | null;
  category: string;
  amount: Money;
}

export interface Goal {
  id: number;
  user_id: number;
  name: string;
  goal_type: GoalKind;
  target_amount: Money;
  current_amount: Money;
  target_date: string | null;
  monthly_contribution: Money;
  priority: number;
  remaining_amount: Money;
  progress_percentage: Money;
  months_remaining: number | null;
  required_monthly_contribution: Money;
  created_at: string;
  updated_at: string;
}

export interface DashboardData {
  user_id: number;
  month: string;
  monthly_income: Money;
  monthly_expenses: Money;
  monthly_expenses_excluding_debt: Money;
  monthly_debt_payment: Money;
  monthly_savings: Money;
  savings_rate: Money;
  monthly_surplus: Money;
  investable_surplus: Money;
  financial_health_score: number;
  emergency_fund: {
    current_amount: Money;
    target_amount: Money;
    remaining_amount: Money;
    coverage_percentage: Money;
  };
  expense_by_category: CategoryAmount[];
  income_vs_expenses: { month: string; income: Money; expenses: Money }[];
  monthly_savings_trend: { month: string; savings: Money }[];
  top_spending_categories: CategoryAmount[];
  goals: Goal[];
}

export interface Transaction {
  id: number;
  user_id: number;
  date: string;
  description: string;
  merchant: string;
  amount: Money;
  transaction_type: TransactionKind;
  category_id: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransactionList {
  items: Transaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface Budget {
  id: number;
  user_id: number;
  category_id: number;
  monthly_limit: Money;
  month: number;
  year: number;
  created_at: string;
  updated_at: string;
}

export interface BudgetStatus {
  budget_id: number;
  category_id: number;
  category: string;
  monthly_limit: Money;
  amount_spent: Money;
  remaining_budget: Money;
  percentage_used: Money;
  status: "ON_TRACK" | "WARNING" | "OVER_BUDGET";
}

export interface SimulationResult {
  invested_amount: Money;
  estimated_interest: Money;
  maturity_value: Money;
  disclaimer?: string | null;
}

export interface AvailableSurplus {
  user_id: number;
  monthly_income: Money;
  monthly_expenses: Money;
  monthly_savings: Money;
  monthly_surplus: Money;
  monthly_debt_payment: Money;
  safety_buffer: Money;
  emergency_fund_gap: Money;
  emergency_fund_monthly_reserve: Money;
  monthly_goal_contributions: Money;
  calculated_investable_surplus: Money;
  available_investable_surplus: Money;
  explanation: string[];
}

export interface FinancialPriority {
  priority_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  purpose: string;
  action: string;
  reason_code: string;
  reason: string;
  related_goal_id: number | null;
}

export interface GoalAnalysis {
  goal_id: number;
  name: string;
  goal_type: string;
  goal_horizon: "VERY_SHORT_TERM" | "SHORT_TERM" | "MEDIUM_TERM" | "LONG_TERM" | "UNSPECIFIED";
  remaining_months: number | null;
  target_amount: Money;
  current_amount: Money;
  funding_gap: Money;
  required_monthly_contribution: Money;
  planned_monthly_contribution: Money;
  funded_monthly_contribution: Money;
  funding_status: "ON_TRACK" | "SLIGHTLY_BEHIND" | "AT_RISK" | "NOT_FEASIBLE_WITH_CURRENT_SURPLUS" | "NEEDS_TARGET_DATE";
}

export interface InvestmentCategoryGuidance {
  name: string;
  description: string;
  risk_level: string;
  liquidity: string;
  typical_time_horizon: string;
  return_type: string;
  market_linked: boolean;
  capital_guarantee_explanation: string;
  best_used_for: string;
  advantages: string[];
  limitations: string[];
  relevance_score: number | null;
  relevance_level: string | null;
  relevance_reason: string | null;
}

export interface InvestmentAllocation {
  purpose: string;
  amount: Money;
  percentage: Money;
  reason_code: string;
  reason: string;
  categories_to_explore: InvestmentCategoryGuidance[];
  related_goal_id: number | null;
}

export interface InvestmentPlan {
  user_id: number;
  currency: string;
  monthly_income: Money;
  monthly_expenses: Money;
  monthly_debt_payment: Money;
  actual_monthly_savings: Money;
  monthly_surplus: Money;
  cash_after_actual_savings: Money;
  existing_goal_commitments: Money;
  cash_after_existing_commitments: Money;
  safety_buffer_target: Money;
  safety_buffer: Money;
  emergency_fund_current: Money;
  emergency_fund_target: Money;
  emergency_fund_gap: Money;
  debt_repayment_reserve: Money;
  short_term_goal_reserve: Money;
  goal_contributions: Money;
  emergency_fund_contribution: Money;
  scheduled_goal_contributions: Money;
  funded_existing_goal_contributions: Money;
  savings_goal_overlap: Money;
  allocation_total: Money;
  funding_ledger: { purpose: string; amount: Money; reason_code: string }[];
  investable_surplus: Money;
  unallocated_buffer: Money;
  financial_priorities: FinancialPriority[];
  allocations: InvestmentAllocation[];
  goal_analysis: GoalAnalysis[];
  warnings: string[];
  methodology: string[];
}

export interface GoalComparison {
  goal: GoalAnalysis;
  risk_tolerance: RiskTolerance;
  liquidity_requirement: string;
  categories_to_explore: InvestmentCategoryGuidance[];
  methodology: string;
}

export interface FinancialHealth {
  user_id: number;
  score: number;
  maximum_score: number;
  components: { name: string; points: number; maximum_points: number; status: string; reason: string }[];
  goal_progress_context: string;
  strengths: string[];
  areas_to_improve: string[];
  deterministic_actions: string[];
}

export interface MonthlyActionPlan {
  user_id: number;
  month: string;
  monthly_income: Money;
  essential_expenses: Money;
  discretionary_expenses: Money;
  debt_obligations: Money;
  monthly_savings: Money;
  monthly_surplus: Money;
  safety_buffer: Money;
  allocations: { purpose: string; amount: Money; reason_code: string }[];
  allocation_total: Money;
  remaining_unallocated: Money;
  total_income_commitment: Money;
  income_limit: Money;
  warnings: string[];
}

export interface AffordabilityInput {
  user_id?: number;
  item_name: string;
  price: string;
  purchase_date: string;
  payment_method: "CASH" | "EMI";
  down_payment?: string;
  monthly_emi?: string;
  tenure_months?: number;
}

export interface AffordabilityResult {
  user_id: number;
  item_name: string;
  price: Money;
  payment_method: "CASH" | "EMI";
  affordability_score: number;
  affordability_status: "COMFORTABLE" | "MANAGEABLE" | "CAUTION" | "HIGH_RISK";
  cash_flow_impact: Money;
  upfront_funding_shortfall: Money;
  emergency_fund_before: Money;
  emergency_fund_after: Money;
  emergency_coverage_months_before: Money;
  emergency_coverage_months_after: Money;
  goal_impact: Money;
  monthly_surplus_before: Money;
  monthly_surplus_after: Money;
  total_emi_commitment: Money;
  debt_burden_before_percent: Money;
  debt_burden_after_percent: Money;
  score_components: Record<string, number>;
  warnings: string[];
  alternative_scenarios: { name: string; purchase_date: string; required_monthly_saving: Money; projected_emergency_fund: Money; projected_goal_contribution: Money; status: string; available_monthly_saving: Money; monthly_saving_shortfall: Money; affordability_score: number; warnings: string[] }[];
  methodology: string[];
}

export type WhatIfType = "INCOME_INCREASE" | "RENT_INCREASE" | "FOOD_SPENDING_REDUCTION" | "SAVINGS_INCREASE" | "GOAL_DELAY";

export interface WhatIfInput {
  scenario_type: WhatIfType;
  amount?: string;
  goal_id?: number;
  delay_months?: number;
  category_ids?: number[];
}

export interface WhatIfSnapshot {
  monthly_income: Money;
  monthly_expenses: Money;
  actual_monthly_savings: Money;
  savings_rate: Money;
  monthly_surplus: Money;
  investable_surplus: Money;
  emergency_fund_months: Money;
  goal_feasibility: GoalAnalysis[];
}

export interface WhatIfResult {
  user_id: number;
  scenario_type: WhatIfType;
  current: WhatIfSnapshot;
  projected: WhatIfSnapshot;
  changes: Record<string, Money | number | string>;
  warnings: string[];
}

export interface FinancialInsights {
  user_id: number;
  coverage_note: string;
  insights: { type: string; severity: string; title: string; metric: string; current_value: Money | null; comparison_value: Money | null; reason_code: string; message: string }[];
}

export interface TransactionInput {
  user_id?: number;
  date: string;
  description: string;
  merchant: string;
  amount: string;
  transaction_type: TransactionKind;
  category_id: number | null;
  notes: string | null;
}

export interface GoalInput {
  user_id?: number;
  name: string;
  goal_type: GoalKind;
  target_amount: string;
  current_amount: string;
  target_date: string | null;
  monthly_contribution: string;
  priority: number;
}

export interface BudgetInput {
  user_id?: number;
  category_id: number;
  monthly_limit: string;
  month: number;
  year: number;
}
