// Session-gated content is resolved at request time, outside instant navigation.
export const instant = false;

import SettingsView from "@/components/settings/settings-view";

export default function SettingsPage() {
  return <SettingsView />;
}