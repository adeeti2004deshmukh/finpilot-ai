import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL?.replace(/\/$/, "");
for (const [name, value] of [["BACKEND_URL", backendUrl], ["NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL]]) {
  if (value) {
    try {
      const parsed = new URL(value);
      if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password || parsed.pathname !== "/" || parsed.search || parsed.hash) throw new Error();
    } catch {
      throw new Error(`${name} must be an HTTP(S) origin without credentials or paths.`);
    }
  }
}
if (process.env.VERCEL_ENV === "production") {
  const direct = process.env.NEXT_PUBLIC_API_URL;
  const target = direct || backendUrl;
  if (!target?.startsWith("https://")) throw new Error("Production requires an HTTPS BACKEND_URL or NEXT_PUBLIC_API_URL.");
}

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  async rewrites() {
    return backendUrl ? [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }] : [];
  },
  async headers() {
    return [
      { source: "/:path*", headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ] },
      { source: "/api/:path*", headers: [{ key: "Cache-Control", value: "no-store" }] },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
