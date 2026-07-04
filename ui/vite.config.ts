import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Prism's API is published on host port 8002 (docker-compose.yml remaps
      // it to avoid clashing with other local stacks bound to 8000).
      "/api": "http://localhost:8002",
      "/webhooks": "http://localhost:8002",
    },
  },
  build: {
    outDir: "dist",
  },
});
