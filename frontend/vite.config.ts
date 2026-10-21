import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    host: "127.0.0.1",
    proxy: {
      "/api/auth": "http://127.0.0.1:8090",
      "/api/tasks": "http://127.0.0.1:8091",
      "/api/notifications": "http://127.0.0.1:8092",
    },
  },
});
