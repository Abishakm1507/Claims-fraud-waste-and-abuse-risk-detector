import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5193,
    // Single origin in development: the API is proxied, so no CORS setup.
    proxy: { "/api": { target: "http://localhost:8732", changeOrigin: true } },
  },
});
