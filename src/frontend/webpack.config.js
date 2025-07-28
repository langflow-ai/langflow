const path = require("path");
require("dotenv").config({ path: path.resolve(__dirname, ".env") });
// Hardcode the backend URL
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";
console.log("Using BACKEND_URL:", BACKEND_URL);
const webpack = require("webpack");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const { ModuleFederationPlugin } = require("webpack").container;
const ReactRefreshWebpackPlugin = require("@pmmmwh/react-refresh-webpack-plugin");
const CopyWebpackPlugin = require("copy-webpack-plugin");

module.exports = (env) => {
  const isDev = env === "development";

  return {
    mode: isDev ? "development" : "production",
    entry: "./src/MFEEntry.tsx",
    
    // Add caching for faster rebuilds
    cache: isDev ? {
      type: 'memory',
    } : false,
    
    // Optimize for development
    optimization: isDev ? {
      removeAvailableModules: false,
      removeEmptyChunks: false,
      splitChunks: false,
    } : {},
    
    output: {
      publicPath: "auto",
      // publicPath: "http://localhost:3030/",
      path: path.resolve(__dirname, "dist"),
      filename: "[name].js",
      chunkFilename: "[name].js",
      clean: true,
    },
    
    // Add watch options for better file watching
    watchOptions: isDev ? {
      aggregateTimeout: 300,
      poll: false,
      ignored: /node_modules/,
    } : {},
    
    performance: {
      hints: false, // Disable performance warnings
    },
    resolve: {
      fallback: {
        process: require.resolve("process/browser"),
      },
      extensions: [".tsx", ".ts", ".js", ".jsx", ".mjs"],
      alias: {
        react: path.resolve("./node_modules/react"),
        "react-dom": path.resolve("./node_modules/react-dom"),
        "@": path.resolve(__dirname, "src"),
      },
    },
    module: {
      rules: [
        {
          test: /\.[jt]sx?$/,
          loader: "babel-loader",
          exclude: /node_modules/,
          options: {
            presets: [
              "@babel/preset-env",
              ["@babel/preset-react", { runtime: "automatic" }],
              "@babel/preset-typescript",
            ],
            plugins: [isDev && require.resolve("react-refresh/babel")].filter(
              Boolean
            ),
          },
        },
        {
          test: /\.s?css$/,
          use: [
            "style-loader", 
            "css-loader", 
            {
              loader: "postcss-loader",
              options: {
                postcssOptions: {
                  plugins: [
                    require('tailwindcss'),
                    require('autoprefixer'),
                  ],
                },
              },
            },
            "sass-loader"
          ],
        },
        {
          test: /\.(png|jpe?g|gif)$/i,
          type: "asset/resource",
        },
        {
          test: /\.svg$/i,
          issuer: /\.[jt]sx?$/,
          resourceQuery: /react/,
          use: ["@svgr/webpack"],
        },
        {
          test: /\.svg$/i,
          type: "asset/resource",
          resourceQuery: { not: [/react/] },
        },
        {
          test: /\.m?js$/,
          resolve: {
            fullySpecified: false,
          },
        },
      ],
    },
    plugins: [
      new HtmlWebpackPlugin({ template: "./public/index.html" }),
      new CopyWebpackPlugin({
        patterns: [
          {
            from: path.resolve(__dirname, "public/favicon.ico"),
            to: "favicon.ico",
          },
        ],
      }),
      new ModuleFederationPlugin({
        name: "langflow",
        filename: "remoteEntry.js",
        exposes: {
          "./LangflowApp": "./src/MFEEntry.tsx",
        },
        shared: {
          react: { 
            singleton: true, 
            eager: true, 
            requiredVersion: false,
            // Add HMR support for React
            ...(isDev && { version: false })
          },
          "react-dom": { 
            singleton: true, 
            eager: true, 
            requiredVersion: false,
            // Add HMR support for React DOM  
            ...(isDev && { version: false })
          },
        },
        // Add development optimizations
        ...(isDev && {
          library: {
            type: "var",
            name: "langflow"
          }
        })
      }),
      new webpack.ProvidePlugin({
        process: "process/browser",
        React: "react",
      }),
      new webpack.DefinePlugin({
        "import.meta.env": JSON.stringify({
          CI: process.env.CI ?? false,
          LANGFLOW_AUTO_LOGIN: process.env.LANGFLOW_AUTO_LOGIN ?? true,
          BACKEND_URL: BACKEND_URL,
          ACCESS_TOKEN_EXPIRE_SECONDS:
            process.env.ACCESS_TOKEN_EXPIRE_SECONDS ?? 60,
        }),
      }),
      isDev && new ReactRefreshWebpackPlugin(),
    ].filter(Boolean),
    devServer: {
      port: 3001,
      hot: true,
      liveReload: false, // Disable live reload in favor of HMR
      client: {
        overlay: {
          errors: true,
          warnings: false, // Only show errors in overlay
        },
        progress: true,
      },
      historyApiFallback: {
        index: "/index.html",
      },
      // Add headers for better HMR
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
        "Access-Control-Allow-Headers": "X-Requested-With, content-type, Authorization",
      },
      proxy: [
        {
          context: ["/api/v1/"],
          target: BACKEND_URL,
          changeOrigin: true,
          secure: false,
          ws: true,
        },
        {
          context: ["/api/v2/"],
          target: BACKEND_URL,
          changeOrigin: true,
          secure: false,
          ws: true,
        },
        {
          context: ["/health"],
          target: BACKEND_URL,
          changeOrigin: true,
          secure: false,
          ws: true,
        },
      ],
    },
  };
};
