// Empty public URL selects the same-origin production /api rewrite.
const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000")).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        ...(init.method && !["GET", "HEAD"].includes(init.method) ? { "X-FinPilot-Request": "1" } : {}),
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("FinPilot could not reach the backend. Check that the API is running.", 0);
  }

  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/") && typeof window !== "undefined") window.dispatchEvent(new Event("finpilot:unauthorized"));
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => typeof item === "object" && item && "msg" in item ? item.msg : "").join(" ")
      : payload?.detail;
    throw new ApiError(typeof detail === "string" ? detail : `Request failed (${response.status}).`, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
