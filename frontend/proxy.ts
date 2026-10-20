import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const directApi = process.env.NEXT_PUBLIC_API_URL;
  const separateOrigin = directApi && new URL(directApi, request.url).origin !== request.nextUrl.origin;
  // A backend host-only cookie is invisible here with direct cross-origin APIs.
  // AuthProvider still gates all private UI using the authenticated /auth/me call.
  if (!separateOrigin && !request.cookies.has(process.env.SESSION_COOKIE_NAME ?? "finpilot_session")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  // Presence is only an early redirect. AuthProvider and every private API
  // validate the actual expiring, server-side session before exposing data.
  return NextResponse.next();
}

export const config = { matcher: ["/", "/dashboard/:path*", "/transactions/:path*", "/budget/:path*", "/goals/:path*", "/investments/:path*", "/affordability/:path*", "/what-if/:path*", "/settings/:path*", "/onboarding/:path*", "/simulator/:path*", "/alerts/:path*", "/ai-coach/:path*"] };
