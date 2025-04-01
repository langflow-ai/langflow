import react from "@vitejs/plugin-react-swc";
import * as dotenv from "dotenv";
import path from "path";
import { defineConfig, loadEnv } from "vite";
import svgr from "vite-plugin-svgr";
import tsconfigPaths from "vite-tsconfig-paths";
import {
  API_ROUTES,
  BASENAME,
  PORT,
  PROXY_TARGET,
} from "./src/customization/config-constants";
import { getBackendRootPath } from "./src/helpers/get-backend-rootpath";

export default defineConfig(async (configEnv) => {
  const env = loadEnv(configEnv.mode, process.cwd(), "");

  const envLangflowResult = dotenv.config({
    path: path.resolve(__dirname, "../../.env"),
  });

  const envLangflow = envLangflowResult.parsed || {};

  const apiRoutes = API_ROUTES || ["^/api/v1/", "^/api/v2/", "/health"];

  const target =
    env.VITE_PROXY_TARGET || PROXY_TARGET || "http://127.0.0.1:7860";

  const rootPath = await getBackendRootPath(target);

  let apiRoutesWithRoot = apiRoutes;
  if (rootPath) {
    apiRoutesWithRoot = apiRoutes.map(route => {
      if (route.startsWith('^')) {
        return `^${rootPath}${route.slice(1)}`;
      }
      return `${rootPath}${route}`;
    });
  }

  const port = Number(env.VITE_PORT) || PORT || 3000;

  const proxyTargets = apiRoutesWithRoot.reduce((proxyObj, route) => {
    proxyObj[route] = {
      target: target,
      changeOrigin: true,
      secure: false,
      ws: true,
    };
    return proxyObj;
  }, {});

  return {
    base: rootPath || BASENAME || "",
    build: {
      outDir: "build",
    },
    define: {
      "process.env.BACKEND_URL": JSON.stringify(
        envLangflow.BACKEND_URL ?? "http://127.0.0.1:7860",
      ),
      "process.env.ACCESS_TOKEN_EXPIRE_SECONDS": JSON.stringify(
        envLangflow.ACCESS_TOKEN_EXPIRE_SECONDS ?? 60,
      ),
      "process.env.CI": JSON.stringify(envLangflow.CI ?? false),
      "process.env.LANGFLOW_AUTO_LOGIN": JSON.stringify(
        envLangflow.LANGFLOW_AUTO_LOGIN ?? true,
      ),
      "process.env.ROOT_PATH": JSON.stringify(rootPath || ""),
    },
    plugins: [react(), svgr(), tsconfigPaths()],
    server: {
      port: port,
      proxy: {
        ...proxyTargets,
      },
    },
  };
});
