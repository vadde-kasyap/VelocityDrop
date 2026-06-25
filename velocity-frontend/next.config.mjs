/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow WSL2 / LAN network interfaces to access the Next.js dev server
  // without triggering cross-origin HMR blocks (the 172.28.x.x is WSL2's virtual adapter)
  allowedDevOrigins: [
    "172.28.208.1",
    "localhost",
    "127.0.0.1",
  ],
};

export default nextConfig;
