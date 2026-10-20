import { apiRequest } from "@/services/api";
import { parseGoalComparison, parseInvestmentCategories, parseInvestmentPlan, parsePlannerGoals } from "@/services/investment-contract";
import type {
  AvailableSurplus,
  AffordabilityInput,
  AffordabilityResult,
  Budget,
  BudgetInput,
  BudgetStatus,
  Category,
  DashboardData,
  FinancialProfile,
  FinancialHealth,
  FinancialInsights,
  Goal,
  GoalInput,
  MonthlyActionPlan,
  SimulationResult,
  Transaction,
  TransactionInput,
  TransactionList,
  User,
  WhatIfInput,
  WhatIfResult,
} from "@/types/api";

export const financeApi = {
  dashboard: () => apiRequest<DashboardData>("/api/me/dashboard"),
  availableSurplus: () => apiRequest<AvailableSurplus>("/api/me/available-surplus"),
  investmentPlan: () => apiRequest<unknown>("/api/me/investment-plan").then(parseInvestmentPlan),
  investmentCategories: () => apiRequest<unknown>("/api/investment/categories").then(parseInvestmentCategories),
  compareGoal: (goalId: number) =>
    apiRequest<unknown>(`/api/me/investment-compare?goal_id=${goalId}`).then(parseGoalComparison),
  financialHealth: () => apiRequest<FinancialHealth>("/api/me/financial-health"),
  monthlyActionPlan: () => apiRequest<MonthlyActionPlan>("/api/me/monthly-plan"),
  financialInsights: () => apiRequest<FinancialInsights>("/api/me/insights"),
  analyzeAffordability: (body: AffordabilityInput) =>
    apiRequest<AffordabilityResult>("/api/affordability/analyze", { method: "POST", body: JSON.stringify(body) }),
  whatIf: (body: WhatIfInput) =>
    apiRequest<WhatIfResult>("/api/me/what-if", { method: "POST", body: JSON.stringify(body) }),
  user: () => apiRequest<User>("/api/me/user"),
  updateUser: (body: Partial<Pick<User, "name" | "age">>) =>
    apiRequest<User>("/api/me/user", { method: "PUT", body: JSON.stringify(body) }),
  profile: () => apiRequest<FinancialProfile>("/api/me/profile"),
  updateProfile: (body: Partial<FinancialProfile>) =>
    apiRequest<FinancialProfile>("/api/me/profile", { method: "PUT", body: JSON.stringify(body) }),
  suggestCategory: (merchant: string, type: string) => apiRequest<{ category_id: number | null }>(`/api/me/category-suggestion?merchant=${encodeURIComponent(merchant)}&transaction_type=${type}`),
  categories: (type?: string) =>
    apiRequest<Category[]>(`/api/categories${type ? `?type=${type}` : ""}`),
  transactions: (params: URLSearchParams) =>
    apiRequest<TransactionList>(`/api/me/transactions?${params.toString()}`),
  createTransaction: (body: TransactionInput) =>
    apiRequest<Transaction>("/api/transactions", { method: "POST", body: JSON.stringify(body) }),
  updateTransaction: (id: number, body: Partial<TransactionInput>) =>
    apiRequest<Transaction>(`/api/transactions/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteTransaction: (id: number) =>
    apiRequest<void>(`/api/transactions/${id}`, { method: "DELETE" }),
  budgets: () => apiRequest<Budget[]>("/api/me/budgets"),
  budgetStatus: (month: number, year: number) =>
    apiRequest<BudgetStatus[]>(`/api/me/budget-status?month=${month}&year=${year}`),
  createBudget: (body: BudgetInput) =>
    apiRequest<Budget>("/api/budgets", { method: "POST", body: JSON.stringify(body) }),
  updateBudget: (id: number, body: Partial<BudgetInput>) =>
    apiRequest<Budget>(`/api/budgets/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteBudget: (id: number) => apiRequest<void>(`/api/budgets/${id}`, { method: "DELETE" }),
  goals: () => apiRequest<unknown>("/api/me/goals").then(parsePlannerGoals),
  createGoal: (body: GoalInput) =>
    apiRequest<Goal>("/api/goals", { method: "POST", body: JSON.stringify(body) }),
  updateGoal: (id: number, body: Partial<GoalInput>) =>
    apiRequest<Goal>(`/api/goals/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteGoal: (id: number) => apiRequest<void>(`/api/goals/${id}`, { method: "DELETE" }),
  simulate: (kind: "sip" | "rd" | "fd" | "compound-growth", body: object) =>
    apiRequest<SimulationResult>(`/api/simulate/${kind}`, { method: "POST", body: JSON.stringify(body) }),
};
