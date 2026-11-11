import { defineConfig, type Plugin } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

const projectEntry: Plugin = {
  name: "project-dev-entry",
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const url = new URL(req.url || "/", "http://localhost");
      if (url.pathname !== "/" && url.pathname !== "/index.html") return next();
      res.statusCode = 302;
      res.setHeader("Location", "/project.html" + url.search);
      res.end();
    });
  },
};

export default defineConfig({
  plugins: [vue(), projectEntry],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: { port: 5175, strictPort: true, proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist-project", rollupOptions: { input: path.resolve(__dirname, "project.html") } },
  base: "./",
});
