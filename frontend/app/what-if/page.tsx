// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import WhatIfView from "@/components/what-if/what-if-view";

export default function WhatIfPage() {
  return <WhatIfView />;
}