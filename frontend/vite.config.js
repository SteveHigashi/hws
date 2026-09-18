import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH || "/",
  server: {
    proxy: {
      "/api": process.env.VITE_HIGASHI_API_URL || "http://localhost:8000",
    },
  },
});
