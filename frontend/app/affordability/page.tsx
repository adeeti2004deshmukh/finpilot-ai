// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import AffordabilityView from "@/components/affordability/affordability-view";

export default function AffordabilityPage() {
  return <AffordabilityView />;
}