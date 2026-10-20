// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import BudgetView from "@/components/budget/budget-view";

export default function BudgetPage() {
  return <BudgetView />;
}