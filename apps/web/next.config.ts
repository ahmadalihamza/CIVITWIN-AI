import type { NextConfig } from "next";

process.env.NEXT_TELEMETRY_DISABLED ??= "1";

const config: NextConfig = {
  poweredByHeader: false,
  devIndicators: false,
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  async rewrites() {
    const backend = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/v1/:path*", destination: backend + "/api/v1/:path*" }];
  },
};

export default config;
