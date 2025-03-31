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
        case "valid_csv":
          result = validCsv(result);
          break;
        case "commands":
          result = validCommands(result);
          break;
      }
    } catch (error) {
      throw new Error(`Error in parser ${parser}`);
    }
  }

  return result;
}
