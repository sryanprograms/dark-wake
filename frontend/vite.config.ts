import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/ws": { target: "http://localhost:8000", ws: true },
      "/scenarios": "http://localhost:8000",
      "/vessels": "http://localhost:8000",
      "/assets": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
