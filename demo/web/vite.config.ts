import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "build", emptyOutDir: true },
  server: {
    port: 5176,
    proxy: {
      "/api": "http://127.0.0.1:18080",
      "/health": "http://127.0.0.1:18080",
    },
  },
});
