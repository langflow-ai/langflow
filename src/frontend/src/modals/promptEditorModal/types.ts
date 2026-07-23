import type { APIClassType } from "@/types/api";

export type PromptSyntaxKind = "fstring" | "mustache";

export interface ValidatePromptPayload {
  name: string;
  template: string;
  frontend_node: APIClassType;
  mustache?: boolean;
}

/**
 * Encapsulates every behavior that differs between the f-string and the
 * mustache prompt editors. The modal body is shared; each divergence found
 * in the original implementations maps to one member here.
 */
export interface PromptSyntaxStrategy {
  kind: PromptSyntaxKind;
  /** Extracts the variable badges shown in the footer (original checkVariables). */
  extractVariables(valueToCheck: string): Set<string>;
  /** Builds the highlighted preview HTML (original coloredContent transform). */
  renderColoredContent(inputValue: string): string;
  /** Builds the validate-prompt mutation payload (mustache adds `mustache: true`). */
  buildValidatePayload(
    fieldName: string,
    template: string,
    nodeClass: APIClassType,
  ): ValidatePromptPayload;
  /** i18n key for the modal header description (mustache only). */
  headerDescriptionKey?: string;
  /** Extra class applied to the preview wrapper (`" m-0"` vs `" bg-muted"`). */
  previewClassName: string;
}
