import react from "@vitejs/plugin-react-swc";
import * as dotenv from "dotenv";
import path from "path";
import { defineConfig, loadEnv } from "vite";
import istanbul from "vite-plugin-istanbul";
import svgr from "vite-plugin-svgr";
import tsconfigPaths from "vite-tsconfig-paths";
import { normalizeBasePath } from "./src/customization/base-path";
import {
  API_ROUTES,
  BASENAME,
  PORT,
  PROXY_TARGET,
} from "./src/customization/config-constants";
import { createAccessTokenExpireSecondsDefinition } from "./vite-env-definitions";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  const envLangflowResult = dotenv.config({
    path: path.resolve(__dirname, "../../.env"),
  });

  const envLangflow = envLangflowResult.parsed || {};

  const apiRoutes = API_ROUTES || ["^/api/v1/", "^/api/v2/", "/health"];
  const basePath = normalizeBasePath(env.VITE_LANGFLOW_BASE_PATH ?? BASENAME);
  const escapedBasePath = basePath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const target =
    env.VITE_PROXY_TARGET || PROXY_TARGET || "http://localhost:7860";

  const port = Number(env.VITE_PORT) || PORT || 3000;

  const proxyTargets = apiRoutes.reduce((proxyObj, route) => {
    const prefixedRoute = route.startsWith("^")
      ? `^${escapedBasePath}${route.slice(1)}`
      : `${basePath}${route}`;
    proxyObj[prefixedRoute] = {
      target: target,
      changeOrigin: true,
      secure: false,
      ws: true,
      rewrite: (requestPath: string) =>
        requestPath.slice(basePath.length) || "/",
    };
    return proxyObj;
  }, {});

  return {
    // Relative build assets allow the backend to select the prefix at startup.
    base: command === "serve" ? `${basePath}/` : "./",
    build: {
      outDir: "build",
    },
    define: {
      ...createAccessTokenExpireSecondsDefinition(
        envLangflow.ACCESS_TOKEN_EXPIRE_SECONDS,
      ),
      "import.meta.env.BACKEND_URL": JSON.stringify(
        envLangflow.BACKEND_URL ?? "http://localhost:7860",
      ),
      "import.meta.env.CI": JSON.stringify(envLangflow.CI ?? false),
      __LANGFLOW_AUTO_LOGIN__: JSON.stringify(
        envLangflow.LANGFLOW_AUTO_LOGIN ?? true,
      ),
      "import.meta.env.LANGFLOW_MCP_COMPOSER_ENABLED": JSON.stringify(
        envLangflow.LANGFLOW_MCP_COMPOSER_ENABLED ?? "true",
      ),
      // Compile-time hard kill switch for the palette Bundle-header
      // Reload action.  The actual user-facing gate is the runtime
      // ``enable_extension_reload`` flag served from ``/config`` (mirrors
      // ``LANGFLOW_ENABLE_EXTENSION_RELOAD``), so a packaged frontend
      // built once can still light up the button when an operator opts
      // the backend in via ``--env-file`` or ``lfx extension dev``.
      // Default ``true`` here means the bundle SHIPS the UI; corporate
      // Mode B/C builds that want to drop the code entirely can set
      // ``LANGFLOW_EXTENSION_RELOAD_ENABLED=false`` in ``.env`` to dead-code-
      // eliminate the Reload UI at build time.
      "import.meta.env.LANGFLOW_EXTENSION_RELOAD_ENABLED": JSON.stringify(
        envLangflow.LANGFLOW_EXTENSION_RELOAD_ENABLED ?? "true",
      ),
      "import.meta.env.LANGFLOW_WXO_UTM_SOURCE": JSON.stringify(
        envLangflow.LANGFLOW_WXO_UTM_SOURCE ?? "langflow",
      ),
    },
    plugins: [
      {
        name: "langflow-dev-base",
        apply: "serve",
        transformIndexHtml(html) {
          return html.replace(
            '<base href="/" />',
            `<base href="${basePath}/" />`,
          );
        },
      },
      react(),
      svgr(),
      tsconfigPaths(),
      istanbul({
        include: "src/**/*",
        extension: [".ts", ".tsx", ".js", ".jsx"],
        requireEnv: false,
      }),
    ],
    server: {
      port: port,
      proxy: {
        ...proxyTargets,
      },
    },
  };
});
