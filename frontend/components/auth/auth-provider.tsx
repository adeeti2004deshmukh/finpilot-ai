"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiRequest, ApiError } from "@/services/api";
import { ErrorState, LoadingSkeleton } from "@/components/ui/states";
import { announceAccountChange, authTabId } from "@/services/auth-events";

export interface AuthUser { id: number; name: string; email: string; age: number | null; is_demo: boolean; onboarding_completed: boolean }
const AuthContext = createContext<{ user: AuthUser | null; logout: () => Promise<void> }>({ user: null, logout: async () => {} });
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const publicRoute = pathname === "/login" || pathname === "/register";
  useEffect(() => {
    let cancelled = false;
    apiRequest<AuthUser>("/api/auth/me").then((value) => { if (!cancelled) setUser(value); })
      .catch((reason) => { if (!cancelled && !(reason instanceof ApiError && reason.status === 401)) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    const expired = () => {
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- Expiry must discard cached private account state.
      window.location.assign("/login");
    };
    window.addEventListener("finpilot:unauthorized", expired);
    return () => { cancelled = true; window.removeEventListener("finpilot:unauthorized", expired); };
  }, []);
  useEffect(() => {
    const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel("finpilot-account");
    if (channel) channel.onmessage = (event) => { if (event.data?.tab !== authTabId) window.location.reload(); };
    const restored = (event: PageTransitionEvent) => { if (event.persisted) window.location.reload(); };
    window.addEventListener("pageshow", restored);
    return () => { channel?.close(); window.removeEventListener("pageshow", restored); };
  }, []);
  useEffect(() => {
    if (loading || error) return;
    if (!user && !publicRoute) router.replace("/login");
    else if (user && !user.onboarding_completed && pathname !== "/onboarding") router.replace("/onboarding");
    else if (user?.onboarding_completed && (publicRoute || pathname === "/onboarding")) router.replace("/");
  }, [loading, error, user, pathname, publicRoute, router]);
  async function logout() {
    await apiRequest("/api/auth/logout", { method: "POST" });
    announceAccountChange();
    // Full navigation discards all prior account state, including cached charts.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- Logout must discard cached private account state.
    window.location.assign("/login");
  }
  if (error && !publicRoute) return <main className="auth-layout"><ErrorState message={error} onRetry={() => window.location.reload()} /></main>;
  const permitted = publicRoute ? !user : Boolean(user && (pathname === "/onboarding" ? !user.onboarding_completed : user.onboarding_completed));
  return <AuthContext.Provider value={{ user, logout }}>{!publicRoute && (loading || !permitted) ? <main className="auth-layout"><LoadingSkeleton rows={3} /></main> : children}</AuthContext.Provider>;
}
