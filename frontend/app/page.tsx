// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import DashboardView from "@/components/dashboard/dashboard-view";

export default function Home() {
  return <DashboardView />;
}
