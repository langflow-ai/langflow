/// <reference types='vitest' />

import react from "@vitejs/plugin-react-swc";
import { cpSync, writeFileSync } from "fs";
import { resolve } from "path";
import { defineConfig } from "vite";

export default defineConfig({
  root: __dirname,
  cacheDir: "../node_modules/.vite/ui-components",

  plugins: [
    react(),
    // Note: Add vite-plugin-dts when available
    // dts({
    //   entryRoot: 'src',
    //   tsconfigPath: 'tsconfig.lib.json',
    // }),
  ],

  // Configuration for building your library.
  build: {
    outDir: "../dist/ui-components",
    reportCompressedSize: true,
    commonjsOptions: {
      transformMixedEsModules: true,
    },
    lib: {
      // Could also be a dictionary or array of multiple entry points.
      entry: resolve(__dirname, "src/index.ts"),
      name: "LangflowUIComponents",
      fileName: "index",
      // Change this to the formats you want to support.
      formats: ["es", "cjs"],
    },
    rollupOptions: {
      // External packages that shouldn't be bundled into your library.
      external: ["react", "react-dom", "react/jsx-runtime"],
      output: {
        // Provide global variables to use in the UMD build
        globals: {
          react: "React",
          "react-dom": "ReactDOM",
          "react/jsx-runtime": "jsx",
        },
      },
    },
  },

  test: {
    globals: true,
    cache: {
      dir: "../node_modules/.vitest",
    },
    environment: "jsdom",
    include: ["src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
  },
});
