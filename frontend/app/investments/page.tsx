// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import InvestmentsView from "@/components/investments/investments-view";

export default function InvestmentsPage() {
  return <InvestmentsView />;
}