import type { NextConfig } from "next";

const backendUrl =
  process.env.BACKEND_URL?.replace(/\/$/, "") || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone", // self-contained server for the Docker image (see Dockerfile)
  // Lets two builds be served side by side (e.g. an interleaved A/B performance comparison).
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
