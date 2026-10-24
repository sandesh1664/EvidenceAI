import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Preserve the absolute localhost redirect; Next otherwise treats loopback hosts as identical.
  skipProxyUrlNormalize:
    process.env.NODE_ENV === "development" &&
    (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(
      /\/$/,
      "",
    ) === "http://localhost:8000",
  // Never let acceptance builds invalidate an operator's running dev server.
  distDir: process.env.EVIDENCEAI_E2E === "1" ? ".next-e2e" : ".next",
  output: "standalone",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
      {
        source: "/workspaces/:path*",
        headers: [
          { key: "Cache-Control", value: "private, no-store, max-age=0" },
        ],
      },
      {
        source: "/settings",
        headers: [
          { key: "Cache-Control", value: "private, no-store, max-age=0" },
        ],
      },
    ];
  },
  turbopack: {
    rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } },
  },
};
export default nextConfig;
