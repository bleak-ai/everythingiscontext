import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API calls to a running `gcontext up` server.
// Point elsewhere with VITE_API=http://127.0.0.1:4299 npm run dev
const API = process.env.VITE_API || "http://127.0.0.1:4242";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5179,
    strictPort: true,
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/status": { target: API, changeOrigin: true },
    },
  },
});
