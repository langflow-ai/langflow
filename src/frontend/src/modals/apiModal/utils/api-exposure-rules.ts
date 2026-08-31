/**
 * Frontend mirror of the tweak-refusal rules enforced by the backend in
 * `src/lfx/src/lfx/utils/flow_validation.py` and applied in
 * `lfx.processing.process.apply_tweaks`.
 *
 * WHY THIS EXISTS: `apply_tweaks` silently drops a tweak aimed at a code
 * field or a protected sink — it only logs a warning, which an API caller
 * never sees. Without this mirror the parameters panel offers an "API"
 * toggle on those fields and the generated snippet advertises them, so the
 * UI promises an input the backend will refuse. The mirror lets the UI stop
 * making that promise.
 *
 * THIS IS NOT THE ENFORCEMENT. The backend remains the only authority: any
 * caller can post a tweak without going through this UI, and `apply_tweaks`
 * is what refuses it. Never weaken the backend check because "the frontend
 * already blocks it".
 *
 * KEEPING IT HONEST: `test_frontend_mirrors_tweak_refusal_rules` (in
 * `src/lfx/tests/unit/utils/test_flow_validation.py`) parses this file and
 * fails if either side gains or loses an entry.
 */

import { LANGFLOW_SUPPORTED_TYPES } from "@/constants/constants";
import type { InputFieldType } from "@/types/api";

/**
 * Component types whose nodes can execute code. Mirrors
 * `CODE_EXECUTION_COMPONENT_TYPES`.
 */
export const CODE_EXECUTION_COMPONENT_TYPES: ReadonlySet<string> = new Set([
  "CSVAgent",
  "CodeAct Agent (Smolagents)",
  "CodeActAgentSmolagents",
  "Cuga",
  "LambdaFilterComponent",
  "OpenDsStar Agent",
  "OpenDsStarAgent",
  "Python Code Structured",
  "PythonCodeStructuredTool",
  "Python Function",
  "PythonFunction",
  "PythonFunctionComponent",
  "Python Interpreter",
  "PythonREPLComponent",
  "Python REPL",
  "PythonREPLToolComponent",
  "PythonREPLTool",
  "Smart Transform",
]);

/**
 * Field names that carry executable code or define the sandbox boundary on a
 * code-execution component. Most are plain-text inputs (template type "str"),
 * so a type check does not catch them. Mirrors `CODE_EXECUTION_FIELD_NAMES`.
 * The conventional "code" field name is blocked globally, not listed here.
 */
export const CODE_EXECUTION_FIELD_NAMES: ReadonlySet<string> = new Set([
  "allow_dangerous_code",
  "function_code",
  "python_code",
  "tool_code",
  "filter_instruction",
  "global_imports",
]);

/**
 * Component inputs that cross a privileged sink boundary and must keep the
 * value stored by the flow author. Mirrors
 * `PROTECTED_TWEAK_FIELDS_BY_COMPONENT`.
 */
export const PROTECTED_TWEAK_FIELDS_BY_COMPONENT: Readonly<
  Record<string, ReadonlySet<string>>
> = {
  SQLComponent: new Set(["database_url", "query"]),
};

/**
 * True when the backend would refuse a tweak on this field, so the UI must
 * not advertise it as an API input.
 */
export const isBackendRefusedField = (
  componentType: string | undefined,
  fieldName: string,
  fieldType: string | undefined,
): boolean => {
  if (fieldType === "code" || fieldName === "code") return true;
  if (
    componentType !== undefined &&
    CODE_EXECUTION_COMPONENT_TYPES.has(componentType) &&
    CODE_EXECUTION_FIELD_NAMES.has(fieldName)
  ) {
    return true;
  }
  return (
    componentType !== undefined &&
    (PROTECTED_TWEAK_FIELDS_BY_COMPONENT[componentType]?.has(fieldName) ??
      false)
  );
};

/**
 * Types whose value is an editable literal a tweak can carry. Handle-only
 * inputs are driven by an edge and have no literal to send, so they are not
 * tweakable no matter what the panel shows.
 *
 * `LANGFLOW_SUPPORTED_TYPES` answers a different question — "does this render
 * an inline widget on the node" — and is reused here only for the types it
 * happens to agree on. `model` is listed apart because the node renders it
 * through its own handle path (see computeDisplayHandle) yet its value is a
 * plain literal the tweaks API accepts.
 */
export const isTweakableType = (type: string | undefined): boolean =>
  LANGFLOW_SUPPORTED_TYPES.has(type ?? "") || type === "model";

/**
 * Whether a field can EVER be exposed as an API input, from the field's own
 * nature — independent of runtime state (connected, off-node, tool mode),
 * which is the job of `isFieldExposable`.
 */
export const isFieldTweakable = (
  componentType: string | undefined,
  fieldName: string,
  template: InputFieldType | undefined,
): boolean => {
  if (!template) return false;
  if (fieldName.charAt(0) === "_") return false;
  if (isBackendRefusedField(componentType, fieldName, template.type)) {
    return false;
  }
  return isTweakableType(template.type);
};
