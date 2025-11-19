import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
  plugins: [react()],
  base: "/new/landingpage/",
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});