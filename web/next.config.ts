import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // API 서버 주소(API_URL)가 있으면 /api/* 를 그쪽으로 넘긴다. 브라우저에서는 같은 출처라 세션 쿠키가 그대로 쓰인다.
  async rewrites() {
    const api = process.env.API_URL;
    return api ? [{ source: "/api/:path*", destination: `${api}/api/:path*` }] : [];
  },
  cacheComponents: true,
  partialPrefetching: true,
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
