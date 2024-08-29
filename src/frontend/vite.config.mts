import react from "@vitejs/plugin-react-swc";
import dotenv from "dotenv";
import path from "path";
import { defineConfig } from "vite";
import svgr from "vite-plugin-svgr";
import tsconfigPaths from "vite-tsconfig-paths";
import {
  API_ROUTES,
  BASENAME,
  PORT,
  PROXY_TARGET,
} from "./src/customization/config-constants";

export default defineConfig(({ mode }) => {
  dotenv.config({ path: path.resolve(__dirname, "../../.env") });

  const apiRoutes = API_ROUTES || ["^/api/v1/", "/health"];

  // Use environment variable to determine the target.
  const target =
    process.env.VITE_PROXY_TARGET || PROXY_TARGET || "http://127.0.0.1:7860";

  // Use environment variable to determine the UI server port
  const port = Number(process.env.VITE_PORT) || PORT || 3000;

  const proxyTargets = apiRoutes.reduce((proxyObj, route) => {
    proxyObj[route] = {
      target: target,
      changeOrigin: true,
      secure: false,
      ws: true,
    };
    return proxyObj;
  }, {});

  return {
    basename: (BASENAME || "") + "/",
    build: {
      outDir: "build",
    },
    define: {
      "process.env.BACKEND_URL": JSON.stringify(process.env.BACKEND_URL),
      "process.env.ACCESS_TOKEN_EXPIRE_SECONDS": JSON.stringify(
        process.env.ACCESS_TOKEN_EXPIRE_SECONDS,
      ),
      "process.env.CI": JSON.stringify(process.env.CI),
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
