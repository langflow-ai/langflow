/**
 * Security utilities for mustache template processing.
 * Mirrors the backend validation in lfx/utils/mustache_security.py
 */

// Regex pattern for simple variables only - same as backend
const SIMPLE_VARIABLE_PATTERN = /\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g;

// Patterns for complex mustache syntax that we want to block
const DANGEROUS_PATTERNS = [
  /\{\{\{/, // Triple braces (unescaped HTML in Mustache)
  /\{\{#/, // Conditionals/sections start
  /\{\{\//, // Conditionals/sections end
  /\{\{\^/, // Inverted sections
  /\{\{&/, // Unescaped variables
  /\{\{>/, // Partials
  /\{\{!/, // Comments
  /\{\{\./, // Current context
];

export interface MustacheValidationResult {
  isValid: boolean;
  error?: string;
  variables: string[];
}

/**
 * Validate that a mustache template only contains simple variable substitutions.
 * Returns validation result with extracted variables if valid.
 */
export function validateMustacheTemplate(
  template: string,
): MustacheValidationResult {
  if (!template) {
    return { isValid: true, variables: [] };
  }

  // Check for dangerous patterns
  for (const pattern of DANGEROUS_PATTERNS) {
    if (pattern.test(template)) {
      return {
        isValid: false,
        error:
          "Complex mustache syntax is not allowed. Only simple variable substitution like {{variable}} is permitted.",
        variables: [],
      };
    }
  }

  // Check for unclosed tags - {{ without a matching }}
  // Find all {{ and check each one has a closing }}
  let searchPos = 0;
  while (true) {
    const openPos = template.indexOf("{{", searchPos);
    if (openPos === -1) break;

    const afterOpen = template.slice(openPos + 2);
    const closePos = afterOpen.indexOf("}}");

    if (closePos === -1) {
      // No }} found after this {{
      return {
        isValid: false,
        error: `Invalid template syntax. Check that all {{variables}} have matching closing braces.`,
        variables: [],
      };
    }

    // Move past this {{ to find the next one
    searchPos = openPos + 2 + closePos + 2;
  }

  // Find all {{ }} patterns and validate them
  const allMustachePatterns = template.match(/\{\{[^}]*\}\}/g) || [];
  const simpleVarPattern = /^\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}$/;

  for (const pattern of allMustachePatterns) {
    if (!simpleVarPattern.test(pattern)) {
      return {
        isValid: false,
        error: `Invalid mustache variable: ${pattern}. Only simple variable names like {{variable}} are allowed.`,
        variables: [],
      };
    }
  }

  // Extract valid variables
  const variables: string[] = [];
  const regex = new RegExp(SIMPLE_VARIABLE_PATTERN.source, "g");
  let match: RegExpExecArray | null = regex.exec(template);
  while (match !== null) {
    if (!variables.includes(match[1])) {
      variables.push(match[1]);
    }
    match = regex.exec(template);
  }

  return { isValid: true, variables };
}

/**
 * Extract simple variable names from a mustache template.
 * Only extracts valid {{variable}} patterns, ignoring complex syntax.
 */
export function extractMustacheVariables(template: string): string[] {
  const result = validateMustacheTemplate(template);
  return result.variables;
}
