/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // No rewrites needed: all API calls are client-side.
  // In local dev the browser calls http://localhost:8000 directly (CORS is open).
  // In deployment (experimentalServices) the browser calls /_/backend directly.
  // See src/lib/api.ts → resolveBaseURL() for the runtime URL logic.
};

export default nextConfig;
