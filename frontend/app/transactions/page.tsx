// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import TransactionsView from "@/components/transactions/transactions-view";

export default function TransactionsPage() {
  return <TransactionsView />;
}