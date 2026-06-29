import { defineConfig } from "vite";

// base relatif : indispensable pour que les assets se chargent correctement
// une fois packagés dans la WebView Android/iOS de Capacitor (file://, https://localhost).
export default defineConfig({
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
  },
});
