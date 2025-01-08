import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
  const defaultConfig = {
    plugins: [react()],
    resolve: {
      alias: {
        '@': resolve(__dirname, './src')
      }
    }
  };

  const cssInjectedConfig = {
    injectCode: (cssCode: string) => {
      return `
        if (!window.__styles) window.__styles = {};
        window.__styles["playground-component"] = ${cssCode};
      `;
    },
    topExecutionPriority: false,
  };

  if (command === "build") {
    return {
      ...defaultConfig,
      plugins: [
        ...defaultConfig.plugins,
        cssInjectedByJsPlugin(cssInjectedConfig),
      ],
      define: {
        "process.env.NODE_ENV": '"production"',
      },
      base: "./", // Relative path to the root of the repository
      build: {
        manifest: "manifest.json",
        sourcemap: false,
        cssCodeSplit: false,
        rollupOptions: {
          input: "src/index.ts",
          preserveEntrySignatures: "strict",
          output: {
            format: 'iife',
            entryFileNames: 'index.js',
            chunkFileNames: 'index.js',
            assetFileNames: 'index.[ext]',
            manualChunks: undefined
          },
        },
      },
    };
  } else {
    return {
      ...defaultConfig,
      plugins: [
        ...defaultConfig.plugins,
        cssInjectedByJsPlugin({
          ...cssInjectedConfig,
          dev: { enableDev: true }
        }),
      ],
      define: {
        "process.env.NODE_ENV": '"development"',
      },
      test: {
        globals: true,
        environment: "happy-dom",
        setupFiles: ["./vitest-setup.js", "src/test-utils/setup-mock.ts"],
        coverage: {
          include: ["src/**/*.ts", "src/**/*.tsx"],
          exclude: ["src/**/*.d.ts"],
          thresholds: {
            statements: 80,
            branches: 80,
            lines: 80,
            functions: 80,
          },
          reporter: ["cobertura", "html", "text"],
        },
      },
    };
  }
});
