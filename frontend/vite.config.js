import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5193,
    // Proxy /api to the FastAPI backend so the browser sees a single origin.
    proxy: {
      "/api": {
        target: "http://localhost:8732",
        changeOrigin: true,
      },
    },
  },
});
