import { FieldParserType } from "../types/api";

function toSnakeCase(str: string): string {
  return str.trim().replace(/\s+/g, "_");
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
  return str.toLowerCase();
}

function toUpperCase(str: string): string {
  return str.toUpperCase();
}

export function parseString(
  str: string,
  parsers: FieldParserType[] | FieldParserType,
): string {
  let result = str;

  let parsersArray: FieldParserType[] = [];

  if (typeof parsers === "string") {
    parsersArray = [parsers];
  } else {
    parsersArray = parsers;
  }

  for (const parser of parsersArray) {
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
    }
  }

  return result;
}
