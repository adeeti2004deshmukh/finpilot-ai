import type { Goal, GoalAnalysis, GoalComparison, InvestmentCategoryGuidance, InvestmentPlan } from "@/types/api";

// TypeScript annotations do not validate JSON. Reject incompatible financial
// contracts before render; only optional display metadata may default to empty.
type RecordValue = Record<string, unknown>;

function incompatible(path: string): never {
  throw new Error(`The finance API returned an incompatible response at ${path}. Restart the FinPilot backend with the current project code, then retry.`);
}

function record(value: unknown, path: string): RecordValue {
  if (!value || typeof value !== "object" || Array.isArray(value)) incompatible(path);
  return value as RecordValue;
}

function strings(value: RecordValue, fields: readonly string[], path: string) {
  for (const field of fields) if (typeof value[field] !== "string") incompatible(`${path}.${field}`);
}

function money(value: RecordValue, fields: readonly string[], path: string) {
  for (const field of fields) {
    const amount = value[field];
    if ((typeof amount !== "number" && (typeof amount !== "string" || !/^-?\d+(\.\d+)?$/.test(amount))) || !Number.isFinite(Number(amount))) incompatible(`${path}.${field}`);
  }
}

function list(value: unknown, path: string, optional = false): unknown[] {
  if (optional && value == null) return [];
  if (!Array.isArray(value)) incompatible(path);
  return value;
}

function textList(value: unknown, path: string): string[] {
  return list(value, path, true).map((item, index) => {
    if (typeof item !== "string") incompatible(`${path}[${index}]`);
    return item;
  });
}

function category(value: unknown, path: string): InvestmentCategoryGuidance {
  const item = record(value, path);
  strings(item, ["name", "description", "risk_level", "liquidity", "typical_time_horizon", "return_type", "capital_guarantee_explanation", "best_used_for"], path);
  if (typeof item.market_linked !== "boolean") incompatible(`${path}.market_linked`);
  return { ...item, advantages: textList(item.advantages, `${path}.advantages`), limitations: textList(item.limitations, `${path}.limitations`) } as unknown as InvestmentCategoryGuidance;
}

function goalAnalysis(value: unknown, path: string): GoalAnalysis {
  const item = record(value, path);
  strings(item, ["name", "goal_type", "goal_horizon", "funding_status"], path);
  money(item, ["goal_id", "target_amount", "current_amount", "funding_gap", "required_monthly_contribution", "planned_monthly_contribution", "funded_monthly_contribution"], path);
  if (item.remaining_months !== null && (!Number.isInteger(item.remaining_months) || Number(item.remaining_months) < 0)) incompatible(`${path}.remaining_months`);
  return item as unknown as GoalAnalysis;
}

export function parseInvestmentPlan(value: unknown): InvestmentPlan {
  const plan = record(value, "investment_plan");
  // Check the previously crashing collection first to identify stale servers.
  const ledger = list(plan.funding_ledger, "investment_plan.funding_ledger").map((value, index) => {
    const path = `investment_plan.funding_ledger[${index}]`;
    const line = record(value, path);
    strings(line, ["purpose", "reason_code"], path);
    money(line, ["amount"], path);
    return line;
  });
  strings(plan, ["currency"], "investment_plan");
  money(plan, ["user_id", "monthly_income", "monthly_expenses", "monthly_debt_payment", "actual_monthly_savings", "monthly_surplus", "cash_after_actual_savings", "existing_goal_commitments", "cash_after_existing_commitments", "safety_buffer_target", "safety_buffer", "emergency_fund_current", "emergency_fund_target", "emergency_fund_gap", "debt_repayment_reserve", "short_term_goal_reserve", "goal_contributions", "emergency_fund_contribution", "scheduled_goal_contributions", "funded_existing_goal_contributions", "savings_goal_overlap", "allocation_total", "investable_surplus", "unallocated_buffer"], "investment_plan");
  const priorities = list(plan.financial_priorities, "investment_plan.financial_priorities").map((value, index) => {
    const path = `investment_plan.financial_priorities[${index}]`;
    const item = record(value, path);
    strings(item, ["priority_level", "purpose", "action", "reason_code", "reason"], path);
    return item;
  });
  const allocations = list(plan.allocations, "investment_plan.allocations").map((value, index) => {
    const path = `investment_plan.allocations[${index}]`;
    const item = record(value, path);
    strings(item, ["purpose", "reason_code", "reason"], path);
    money(item, ["amount", "percentage"], path);
    return { ...item, categories_to_explore: list(item.categories_to_explore, `${path}.categories_to_explore`, true).map((item, index) => category(item, `${path}.categories_to_explore[${index}]`)) };
  });
  return {
    ...plan,
    funding_ledger: ledger,
    financial_priorities: priorities,
    allocations,
    goal_analysis: list(plan.goal_analysis, "investment_plan.goal_analysis").map((item, index) => goalAnalysis(item, `investment_plan.goal_analysis[${index}]`)),
    warnings: textList(plan.warnings, "investment_plan.warnings"),
    methodology: textList(plan.methodology, "investment_plan.methodology"),
  } as unknown as InvestmentPlan;
}

export function parseInvestmentCategories(value: unknown): InvestmentCategoryGuidance[] {
  return list(value, "investment_categories", true).map((item, index) => category(item, `investment_categories[${index}]`));
}

export function parseGoalComparison(value: unknown): GoalComparison {
  const comparison = record(value, "goal_comparison");
  strings(comparison, ["risk_tolerance", "liquidity_requirement", "methodology"], "goal_comparison");
  return {
    ...comparison,
    goal: goalAnalysis(comparison.goal, "goal_comparison.goal"),
    categories_to_explore: list(comparison.categories_to_explore, "goal_comparison.categories_to_explore").map((item, index) => {
      const result = category(item, `goal_comparison.categories_to_explore[${index}]`);
      if (!Number.isInteger(result.relevance_score) || Number(result.relevance_score) < 0 || Number(result.relevance_score) > 100 || typeof result.relevance_level !== "string" || typeof result.relevance_reason !== "string") incompatible(`goal_comparison.categories_to_explore[${index}].relevance_score`);
      return result;
    }),
  } as unknown as GoalComparison;
}

export function parsePlannerGoals(value: unknown): Goal[] {
  return list(value, "goals", true).map((value, index) => {
    const path = `goals[${index}]`;
    const goal = record(value, path);
    strings(goal, ["name"], path);
    if (!Number.isInteger(goal.id) || (goal.target_date !== null && typeof goal.target_date !== "string")) incompatible(path);
    return goal as unknown as Goal;
  });
}
