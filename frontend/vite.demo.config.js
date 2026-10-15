// Builds a single self-contained HTML file with the in-browser demo server,
// for sharing a clickable preview without running the backend.
//   npm run build:demo   ->  dist-demo/index.html
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  define: { "import.meta.env.VITE_DEMO": JSON.stringify("1") },
  build: { outDir: "dist-demo", emptyOutDir: true },
});
