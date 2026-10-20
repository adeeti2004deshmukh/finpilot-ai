// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import GoalsView from "@/components/goals/goals-view";

export default function GoalsPage() {
  return <GoalsView />;
}