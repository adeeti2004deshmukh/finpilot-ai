// Public account-change notification only: never store/broadcast session tokens.
export const authTabId = crypto.randomUUID();
export function announceAccountChange() {
  if (typeof BroadcastChannel === "undefined") return;
  const channel = new BroadcastChannel("finpilot-account");
  channel.postMessage({ tab: authTabId });
  channel.close();
}
