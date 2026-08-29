import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Keep build output isolated from the pre-existing Gate 0 artifact directory.
  distDir: ".next-m3",
  async rewrites() {
    const backendOrigin = process.env.ASSEMBLE_API_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backendOrigin}/api/:path*` }];
  },
};

export default nextConfig;
