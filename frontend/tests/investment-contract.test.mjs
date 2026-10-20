import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

// Use the existing TypeScript compiler; no additional test dependency/loader.
const source = readFileSync(new URL("../services/investment-contract.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { parseInvestmentPlan, parseGoalComparison, parseInvestmentCategories, parsePlannerGoals } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

function plan() {
  return {
    user_id: 1, currency: "INR", monthly_income: "65000.00", monthly_expenses: "35000.00", monthly_debt_payment: "5000.00",
    actual_monthly_savings: "4000.00", monthly_surplus: "25000.00", cash_after_actual_savings: "21000.00",
    existing_goal_commitments: "0.00", cash_after_existing_commitments: "21000.00", safety_buffer_target: "5200.00",
    safety_buffer: "5200.00", emergency_fund_current: "55000.00", emergency_fund_target: "180000.00",
    emergency_fund_gap: "125000.00", debt_repayment_reserve: "0.00", short_term_goal_reserve: "0.00",
    goal_contributions: "0.00", emergency_fund_contribution: "15800.00", scheduled_goal_contributions: "0.00",
    funded_existing_goal_contributions: "0.00", savings_goal_overlap: "0.00", allocation_total: "25000.00",
    investable_surplus: "0.00", unallocated_buffer: "0.00", funding_ledger: [], financial_priorities: [],
    allocations: [], goal_analysis: [], warnings: [], methodology: [],
  };
}

test("preserves valid financial values and empty required collections", () => {
  assert.deepEqual(parseInvestmentPlan(plan()), plan());
});

test("identifies the old live API's missing funding_ledger instead of crashing during render", () => {
  const old = plan();
  delete old.funding_ledger;
  assert.throws(() => parseInvestmentPlan(old), /funding_ledger.*Restart the FinPilot backend/);
});

test("does not silently replace mandatory accounting fields with zeros", () => {
  for (const key of ["goal_contributions", "emergency_fund_contribution", "allocation_total", "unallocated_buffer", "savings_goal_overlap"]) {
    const invalid = plan();
    delete invalid[key];
    assert.throws(() => parseInvestmentPlan(invalid), new RegExp(key));
  }
});

test("rejects missing, null and malformed mandatory collections", () => {
  for (const key of ["funding_ledger", "allocations", "financial_priorities", "goal_analysis"]) {
    for (const bad of [undefined, null, {}]) assert.throws(() => parseInvestmentPlan({ ...plan(), [key]: bad }), new RegExp(key));
  }
});

test("defaults optional display arrays without inventing financial data", () => {
  const input = plan();
  delete input.warnings;
  input.methodology = null;
  input.allocations = [{ purpose: "Safety", amount: "5200", percentage: "20.8", reason_code: "SAFETY_BUFFER", reason: "Reserve cash" }];
  const result = parseInvestmentPlan(input);
  assert.deepEqual(result.warnings, []);
  assert.deepEqual(result.methodology, []);
  assert.deepEqual(result.allocations[0].categories_to_explore, []);
  assert.equal(result.actual_monthly_savings, "4000.00");
});

test("rejects invalid nested allocation, ledger and priority rows before render", () => {
  assert.throws(() => parseInvestmentPlan({ ...plan(), funding_ledger: [null] }), /funding_ledger\[0\]/);
  assert.throws(() => parseInvestmentPlan({ ...plan(), allocations: [{}] }), /allocations\[0\]/);
  assert.throws(() => parseInvestmentPlan({ ...plan(), financial_priorities: [{}] }), /financial_priorities\[0\]/);
});

test("rejects malformed optional arrays rather than calling map on an object", () => {
  assert.throws(() => parseInvestmentPlan({ ...plan(), warnings: {} }), /warnings/);
  assert.throws(() => parseInvestmentPlan({ ...plan(), warnings: [null] }), /warnings\[0\]/);
});

test("empty goal and category endpoints are safe; invalid objects are errors", () => {
  assert.deepEqual(parsePlannerGoals(null), []);
  assert.deepEqual(parseInvestmentCategories(undefined), []);
  assert.throws(() => parsePlannerGoals({}), /goals/);
  assert.throws(() => parseInvestmentCategories([null]), /investment_categories\[0\]/);
});

test("comparison rejects an old goal schema missing funded contribution", () => {
  assert.throws(() => parseGoalComparison({ risk_tolerance: "LOW", liquidity_requirement: "HIGH", methodology: "Educational", goal: {
    name: "Travel", goal_type: "TRAVEL", goal_horizon: "SHORT_TERM", funding_status: "ON_TRACK", goal_id: 1,
    target_amount: "10000", current_amount: "0", funding_gap: "10000", required_monthly_contribution: "1000",
    planned_monthly_contribution: "1000", remaining_months: 10,
  }, categories_to_explore: [] }), /funded_monthly_contribution/);
});
