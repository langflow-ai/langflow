import { INVALID_CHARACTERS, regexHighlight } from "@/constants/constants";
import type { APIClassType } from "@/types/api";
import { invalidVariableMessageKey } from "@/utils/promptVariables";
import varHighlightHTML from "../promptModal/utils/var-highlight-html";
import type { PromptSyntaxStrategy } from "./types";

// Simple regex to extract mustache variables - only matches valid {{variable_name}} patterns
const SIMPLE_VARIABLE_PATTERN = /\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g;

const escapeHtml = (value: string): string =>
  value.replace(/</g, "&lt;").replace(/>/g, "&gt;");

export const fstringStrategy: PromptSyntaxStrategy = {
  kind: "fstring",
  extractVariables(valueToCheck: string): Set<string> {
    // Match *any* brace run around an identifier
    const regex = /(\{+)([^{}]+)(\}+)/g;
    const matches: string[] = [];
    let match: RegExpExecArray | null = regex.exec(valueToCheck);

    while (match) {
      const [openRun, varName, closeRun] = [match[1], match[2], match[3]];

      // keep only odd, balanced runs (actual variables)
      if (openRun.length === closeRun.length && openRun.length % 2 === 1) {
        matches.push(`{${varName}}`); // normalise to single-brace form
      }
      match = regex.exec(valueToCheck);
    }

    const invalid_chars: string[] = [];
    const fixed_variables: string[] = [];
    const input_variables = matches;
    for (const variable of input_variables) {
      const new_var = variable;
      for (const char of INVALID_CHARACTERS) {
        if (variable.includes(char)) {
          invalid_chars.push(new_var);
        }
      }
      fixed_variables.push(new_var);
      if (new_var !== variable) {
        const index = input_variables.indexOf(variable);
        if (index !== -1) {
          input_variables.splice(index, 1, new_var);
        }
      }
    }

    return new Set(matches.filter((word) => !invalid_chars.includes(word)));
  },
  renderColoredContent(
    inputValue: string,
    translate: (key: string) => string,
  ): string {
    return escapeHtml(typeof inputValue === "string" ? inputValue : "")
      .replace(
        regexHighlight,
        (match, codeFence, openRun, varName, closeRun) => {
          // regexHighlight captures four groups: the ```code fence```, then the opening
          // brace run, the name and the closing brace run. Omitting codeFence here shifted
          // every group by one, so lenOpen was always 0 and nothing was ever highlighted.

          // 1) Leave ```code``` blocks untouched
          if (codeFence) return match;

          // 2) Only highlight when both sides are the *same* length and that
          //    length is odd (   1,3,5,…  ).
          const lenOpen = openRun?.length ?? 0;
          const lenClose = closeRun?.length ?? 0;
          const isVariable = lenOpen === lenClose && lenOpen % 2 === 1;

          if (!isVariable) return match; // even-brace runs ⇒ escape, no highlight

          // 3) Number of literal braces each side = floor(lenOpen / 2)
          const literal = "{".repeat(Math.floor(lenOpen / 2));
          const invalidKey = invalidVariableMessageKey(varName);
          return (
            literal +
            varHighlightHTML({
              name: varName,
              // The braces belong inside the highlight, as the node preview renders them.
              // `literal` above only carries the extra braces of an escaped run.
              addCurlyBraces: true,
              invalidTitle: invalidKey ? translate(invalidKey) : undefined,
            }) +
            literal.replace(/\{/g, "}") // same amount of closing braces
          );
        },
      )
      .replace(/\n/g, "<br />");
  },
  buildValidatePayload(
    fieldName: string,
    template: string,
    nodeClass: APIClassType,
  ) {
    return { name: fieldName, template, frontend_node: nodeClass };
  },
  previewClassName: " m-0",
};

export const mustacheStrategy: PromptSyntaxStrategy = {
  kind: "mustache",
  extractVariables(valueToCheck: string): Set<string> {
    // Extract only valid mustache variables {{variable_name}}
    const matches: string[] = [];
    const regex = new RegExp(SIMPLE_VARIABLE_PATTERN.source, "g");
    let match: RegExpExecArray | null = regex.exec(valueToCheck);

    while (match !== null) {
      const varName = match[1];
      if (!matches.includes(varName)) {
        matches.push(varName);
      }
      match = regex.exec(valueToCheck);
    }

    return new Set(matches.map((v) => `{{${v}}}`));
  },
  renderColoredContent(
    inputValue: string,
    translate: (key: string) => string,
  ): string {
    return escapeHtml(typeof inputValue === "string" ? inputValue : "")
      .replace(/\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g, (match, varName) => {
        const invalidKey = invalidVariableMessageKey(varName);
        return varHighlightHTML({
          name: match,
          addCurlyBraces: false,
          variableName: varName,
          invalidTitle: invalidKey ? translate(invalidKey) : undefined,
        });
      })
      .replace(/\n/g, "<br />");
  },
  buildValidatePayload(
    fieldName: string,
    template: string,
    nodeClass: APIClassType,
  ) {
    return {
      name: fieldName,
      template,
      frontend_node: nodeClass,
      mustache: true,
    };
  },
  headerDescriptionKey: "dialog.mustachePrompt",
  previewClassName: " bg-muted",
};
