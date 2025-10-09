import { z } from "zod";

/**
 * Environment variable validators for AI Studio
 * Based on genesis-frontend validation patterns
 */
export const validator = {
  /**
   * Validates a string environment variable
   */
  string: () => z.string().min(1, "String cannot be empty"),

  /**
   * Validates an optional string environment variable
   */
  optionalString: () => z.string().transform((val) => val === "" ? undefined : val).optional(),

  /**
   * Validates a URL environment variable
   */
  url: () =>
    z.string()
     .min(1, "URL cannot be empty")
     .url("Must be a valid URL"),

  /**
   * Validates an optional URL environment variable
   */
  optionalUrl: () =>
    z.string()
     .transform((val) => val === "" ? undefined : val)
     .optional()
     .refine((val) => !val || /^https?:\/\//.test(val), "Must be a valid URL if provided"),

  /**
   * Validates a boolean environment variable
   */
  boolean: () =>
    z.string()
     .transform((val) => val.toLowerCase() === "true")
     .pipe(z.boolean()),

  /**
   * Validates an optional boolean environment variable
   */
  optionalBoolean: () =>
    z.string()
     .transform((val) => val === "" ? undefined : val?.toLowerCase() === "true")
     .optional(),

  /**
   * Validates a comma-separated array environment variable
   */
  array: () =>
    z.string()
     .transform((val) => val ? val.split(",").map(s => s.trim()).filter(Boolean) : [])
     .pipe(z.array(z.string())),

  /**
   * Validates a log level environment variable
   */
  logLevel: () =>
    z.enum(["debug", "info", "warn", "error"])
     .default("info"),
};