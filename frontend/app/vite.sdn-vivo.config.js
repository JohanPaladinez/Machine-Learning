import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Compilación opcional del panel nuevo; conserva dist y la entrada original.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist-sdn-vivo-v1",
    emptyOutDir: false,
    rolldownOptions: { input: fileURLToPath(new URL("./sdn-vivo.html", import.meta.url)) },
  },
});
