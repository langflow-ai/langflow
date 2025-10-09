import { envSchema, type EnvConfig, type RawEnvConfig } from "./env.schema";
import { ZodError } from "zod";

/**
 * Environment variable validation using Zod for AI Studio
 * Based on genesis-frontend pattern
 */
export const validateEnv = (env: Record<string, any>): EnvConfig => {
  const toCamelCase = (str: string): string => {
    return str
      .split("_")
      .map((word, index) =>
        index === 0
          ? word.toLowerCase()
          : word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
      )
      .join("");
  };

  try {
    console.log("🔍 About to validate env with schema...");
    const validatedEnv = envSchema.parse(env) as RawEnvConfig;
    console.log("🔍 Validation successful, validated env:", validatedEnv);

    const processedEnv: Record<string, any> = {};

    for (const [key, value] of Object.entries(validatedEnv)) {
      if (value !== undefined) {
        const camelKey = toCamelCase(key.replace("VITE_", ""));
        processedEnv[camelKey] = value;
      }
    }

    return processedEnv as EnvConfig;
  } catch (error) {
    if (error instanceof ZodError) {
      const validationErrors = error.issues.map((err) => `${err.path.join(".")}: ${err.message}`);

      console.error("AI Studio Environment Configuration Errors:", {
        errors: validationErrors,
        providedEnv: env,
      });

      const errorHtml = `
        <div style="
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background-color: rgb(15, 23, 42);
          padding: 1rem;
          font-family: system-ui, -apple-system, sans-serif;
          color: white;
        ">
          <div style="
            max-width: 40rem;
            width: 100%;
            background-color: rgb(127, 29, 29);
            border-radius: 0.5rem;
            padding: 2rem;
            border: 1px solid rgb(185, 28, 28);
          ">
            <div style="display: flex; align-items: center; margin-bottom: 1rem;">
              <div style="
                width: 2rem;
                height: 2rem;
                background-color: rgb(220, 38, 38);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 1rem;
              ">
                ⚠️
              </div>
              <h3 style="
                font-size: 1.5rem;
                font-weight: 600;
                color: rgb(254, 242, 242);
                margin: 0;
              ">
                AI Studio Environment Configuration Error
              </h3>
            </div>
            <div style="
              margin-bottom: 1rem;
              font-size: 1rem;
              color: rgb(252, 165, 165);
            ">
              <p style="margin: 0 0 1rem 0;">
                ${validationErrors.length} environment variable${validationErrors.length > 1 ? "s" : ""} failed validation.
              </p>
              <p style="margin: 0;">
                Please check the console for details and ensure all required variables are set correctly.
              </p>
            </div>
            <div style="
              background-color: rgb(127, 29, 29);
              border-radius: 0.25rem;
              padding: 1rem;
              font-family: monospace;
              font-size: 0.875rem;
              border: 1px solid rgb(185, 28, 28);
            ">
              Required variables: VITE_BACKEND_URL, VITE_API_PREFIX
            </div>
          </div>
        </div>
      `;

      document.body.innerHTML = errorHtml;

      throw new Error(
        `AI Studio environment configuration validation failed:\n\n${validationErrors.join("\n")}\n`
      );
    }

    throw error;
  }
};

/**
 * Initialize and validate AI Studio environment configuration
 */
export const envConfig = (() => {
  const isProd = typeof window !== "undefined";
  const windowEnvVars = isProd ? (window as any)._env_ : null;
  const env = import.meta.env?.DEV ? import.meta.env : windowEnvVars;

  // Debug logging
  console.log("🔍 Debug - isProd:", isProd);
  console.log("🔍 Debug - import.meta.env:", import.meta.env);
  console.log("🔍 Debug - env object:", env);

  if (env) {
    const config = validateEnv(env);

    if (import.meta.env?.DEV) {
      console.info("🔧 AI Studio environment configuration loaded successfully with Zod validation");
      console.log("🔧 Environment configuration:", JSON.stringify(config, null, 2));
    }

    return Object.freeze(config);
  }

  return Object.freeze({} as EnvConfig);
})();

// Export types for use throughout the application
export type { EnvConfig, RawEnvConfig } from "./env.schema";