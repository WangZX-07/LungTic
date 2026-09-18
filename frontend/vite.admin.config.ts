import { defineConfig, type Plugin } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

const adminEntry: Plugin = {
  name: "admin-dev-entry",
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const url = new URL(req.url || "/", "http://localhost");
      if (url.pathname !== "/" && url.pathname !== "/index.html") {
        next();
        return;
      }
      res.statusCode = 302;
      res.setHeader("Location", "/admin.html" + url.search);
      res.end();
    });
  },
};

export default defineConfig({
  plugins: [vue(), adminEntry],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: { port: 5174, strictPort: true, proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist-admin", rollupOptions: { input: path.resolve(__dirname, "admin.html") } },
  base: "./",
});
