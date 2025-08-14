import DOMPurify from "dompurify";
import React from "react";
import type { FieldParserType } from "../types/api";

function toSnakeCase(str: string): string {
  return str.trim().replace(/[-\s]+/g, "_");
}

function toCamelCase(str: string): string {
  return str
    .replace(/[-_\s]+(.)?/g, (_, c) => (c ? c.toUpperCase() : ""))
    .replace(/^[A-Z]/, (c) => c.toLowerCase());
}

function toPascalCase(str: string): string {
  return str
    .replace(/[-_\s]+(.)?/g, (_, c) => (c ? c.toUpperCase() : ""))
    .replace(/^[a-z]/, (c) => c.toUpperCase());
}

function toKebabCase(str: string): string {
  return str
    .replace(/([A-Z])/g, " $1")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[_]+/g, "-");
}

function toLowerCase(str: string): string {
  return str?.toLowerCase();
}

function toUpperCase(str: string): string {
  return str?.toUpperCase();
}

function toSpaceCase(str: string): string {
  return str
    .trim()
    .replace(/[_\s-]+/g, " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function noBlank(str: string): string {
  const trim = str.trim();
  if (trim === "") {
    throw new Error("String is blank");
  }
  return trim;
}

function validCsv(str: string): string {
  return str.trim().replace(/\s+/g, ",");
}

function validCommands(str: string): string {
  return str
    .trim()
    .split(/[\s,]+/)
    .flatMap((cmd) => {
      cmd = cmd.trim();
      cmd = cmd.replace(/\\/g, "/");
      return cmd
        .split("/")
        .filter((part) => part.length > 0)
        .map((part) => `/${part}`);
    })
    .filter((cmd) => cmd.length > 1)
    .join(", ");
}

function sanitizeMcpName(str: string, maxLength: number = 46): string {
  if (!str || !str.trim()) {
    return "";
  }

  let name = str;

  // Remove emojis using standard regex patterns (without unicode flags)
  // This covers most common emoji ranges using surrogate pairs
  name = name.replace(/[\uD83C-\uDBFF][\uDC00-\uDFFF]/g, ""); // Most emojis
  name = name.replace(/[\u2600-\u27BF]/g, ""); // Misc symbols and dingbats
  name = name.replace(/[\uFE00-\uFE0F]/g, ""); // Variation selectors
  name = name.replace(/\u200D/g, ""); // Zero width joiner

  // Normalize unicode characters to remove diacritics
  name = name.normalize("NFD").replace(/[\u0300-\u036f]/g, "");

  // Replace spaces and special characters with underscores
  name = name.replace(/[^\w\s-]/g, ""); // Keep only word chars, spaces, and hyphens
  name = name.replace(/[-\s]+/g, "_"); // Replace spaces and hyphens with underscores
  name = name.replace(/_+/g, "_"); // Collapse multiple underscores

  // Remove leading/trailing underscores
  name = name.replace(/^_+|_+$/g, "");

  // Ensure it starts with a letter or underscore (not a number)
  if (name && /^\d/.test(name)) {
    name = `_${name}`;
  }

  // Convert to lowercase
  name = name.toLowerCase();

  // Truncate to max length
  if (name.length > maxLength) {
    name = name.substring(0, maxLength).replace(/_+$/, "");
  }

  // If empty after sanitization, provide a default
  if (!name) {
    name = "unnamed";
  }

  return name;
}

export function parseString(
  str: string,
  parsers: FieldParserType[] | FieldParserType,
): string {
  let result = str;

  if (result === "") {
    return "";
  }

  if (parsers.includes("no_blank") && result.trim() === "") {
    return "";
  }

  let parsersArray: FieldParserType[] = [];

  if (typeof parsers === "string") {
    parsersArray = [parsers];
  } else {
    parsersArray = parsers;
  }

  for (const parser of parsersArray) {
    try {
      switch (parser) {
        case "snake_case":
          result = toSnakeCase(result);
          break;
        case "camel_case":
          result = toCamelCase(result);
          break;
        case "pascal_case":
          result = toPascalCase(result);
          break;
        case "kebab_case":
          result = toKebabCase(result);
          break;
        case "lowercase":
          result = toLowerCase(result);
          break;
        case "uppercase":
          result = toUpperCase(result);
          break;
        case "no_blank":
          result = noBlank(result);
          break;
        case "space_case":
          result = toSpaceCase(result);
          break;
        case "valid_csv":
          result = validCsv(result);
          break;
        case "commands":
          result = validCommands(result);
          break;
        case "sanitize_mcp_name":
          result = sanitizeMcpName(result);
          break;
      }
    } catch (_error) {
      throw new Error(`Error in parser ${parser}`);
    }
  }

  return result;
}

export const getStatusColor = (status: string): string => {
  const amberStatuses = [
    "initializing",
    "pending",
    "hibernating",
    "hiberated",
    "maintenance",
    "parked",
  ];

  if (amberStatuses.includes(status?.toLowerCase())) {
    return "text-accent-amber-foreground";
  }

  if (status?.toLowerCase() === "terminating") {
    return "red-500";
  }

  return "";
};

export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return "0 Bytes";

  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
};

export const convertStringToHTML = (htmlString: string): JSX.Element => {
  return React.createElement("span", {
    dangerouslySetInnerHTML: { __html: sanitizeHTML(htmlString) },
  });
};

export const sanitizeHTML = (htmlString: string): string => {
  return DOMPurify.sanitize(htmlString);
};

export { sanitizeMcpName };
