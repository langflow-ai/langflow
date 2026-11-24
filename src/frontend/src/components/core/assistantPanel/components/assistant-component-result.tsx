import { Check, FileText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { AgenticResult } from "@/controllers/API/queries/agentic";
import CodeAreaModal from "@/modals/codeAreaModal";
import {
  GHOST_PRIMARY_BUTTON,
  GHOST_SECONDARY_BUTTON,
} from "../helpers/button-styles";

const APPROVED_DISPLAY_DURATION_MS = 3000;

interface FieldInfo {
  name: string;
  type: string;
}

export function formatType(rawType: string): string {
  // e.g. "MessageTextInput" -> "Text", "IntInput" -> "Int", "StrInput" -> "Str"
  return rawType.replace(/Input$/, "").replace(/^Message/, "");
}

export function parseComponentInfo(code: string | undefined) {
  if (!code)
    return {
      description: null,
      inputs: [] as FieldInfo[],
      outputs: [] as FieldInfo[],
    };

  // Extract description
  const descMatch = code.match(/description\s*=\s*"([^"]+)"/);
  const description = descMatch?.[1] || null;

  // Extract inputs with type (e.g. MessageTextInput, IntInput, etc.)
  const inputRegex = /(\w+Input)\(\s*(?:[^)]*?)display_name\s*=\s*"([^"]+)"/gs;
  const inputs: FieldInfo[] = [];
  for (const match of Array.from(code.matchAll(inputRegex))) {
    inputs.push({ name: match[2], type: formatType(match[1]) });
  }

  // Fallback: simpler pattern
  if (inputs.length === 0) {
    const simpleInputRegex =
      /(MessageTextInput|StrInput|IntInput|FloatInput|BoolInput|FileInput|DropdownInput|MultilineInput|SecretStrInput|HandleInput|DataInput)\s*\([^)]*display_name\s*=\s*"([^"]+)"/g;
    for (const match of Array.from(code.matchAll(simpleInputRegex))) {
      inputs.push({ name: match[2], type: formatType(match[1]) });
    }
  }

  // Extract outputs: get display_name and method name, then resolve return type from method signature
  const outputRegex =
    /Output\(\s*(?:[^)]*?)display_name\s*=\s*"([^"]+)"(?:[^)]*?)method\s*=\s*"(\w+)"/gs;
  const outputs: FieldInfo[] = [];
  for (const match of Array.from(code.matchAll(outputRegex))) {
    const methodName = match[2];
    // Look for the method's return type annotation: def method_name(self) -> ReturnType:
    const returnTypeRegex = new RegExp(
      `def\\s+${methodName}\\s*\\([^)]*\\)\\s*->\\s*(\\w+)`,
    );
    const returnMatch = code.match(returnTypeRegex);
    const returnType = returnMatch?.[1] || "Message";
    outputs.push({ name: match[1], type: returnType });
  }

  // Fallback: outputs without method
  if (outputs.length === 0) {
    const simpleOutputRegex =
      /Output\(\s*(?:[^)]*?)display_name\s*=\s*"([^"]+)"/g;
    for (const match of Array.from(code.matchAll(simpleOutputRegex))) {
      outputs.push({ name: match[1], type: "Message" });
    }
  }

  return { description, inputs, outputs };
}

interface AssistantComponentResultProps {
  result: AgenticResult;
  onApprove: () => void;
}

export function AssistantComponentResult({
  result,
  onApprove,
}: AssistantComponentResultProps) {
  const { t } = useTranslation();
  const [showApproved, setShowApproved] = useState(false);
  const [isViewCodeOpen, setIsViewCodeOpen] = useState(false);
  const componentName = result.className || "Custom Component";
  const { description, inputs, outputs } = useMemo(
    () => parseComponentInfo(result.componentCode),
    [result.componentCode],
  );

  useEffect(() => {
    if (showApproved) {
      const timer = setTimeout(() => {
        setShowApproved(false);
      }, APPROVED_DISPLAY_DURATION_MS);
      return () => clearTimeout(timer);
    }
  }, [showApproved]);

  const handleApprove = () => {
    onApprove();
    setShowApproved(true);
  };

  return (
    <div className="max-w-[80%] rounded-md bg-muted/30 px-3 py-3">
      {/* Component header */}
      <div className="mb-2 flex items-center gap-2">
        <FileText className="h-4 w-4 text-foreground/80" />
        <span className="text-sm font-semibold text-foreground">
          {componentName}
        </span>
      </div>

      {/* Component info */}
      <div className="mb-3 flex flex-col gap-3">
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
        {inputs.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-xs font-semibold text-foreground">
              {t("sidebar.category.inputs")}
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {inputs.map((input) => (
                <span
                  key={input.name}
                  className="rounded bg-muted/40 px-1.5 py-0.5 text-xs text-muted-foreground"
                >
                  {input.name}{" "}
                  <span className="text-muted-foreground/60">
                    ({input.type})
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
        {outputs.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-xs font-semibold text-foreground">
              {t("sidebar.category.outputs")}
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {outputs.map((output) => (
                <span
                  key={output.name}
                  className="rounded bg-muted/40 px-1.5 py-0.5 text-xs text-muted-foreground"
                >
                  {output.name}{" "}
                  <span className="text-muted-foreground/60">
                    ({output.type})
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {showApproved ? (
          <div className="flex h-7 items-center gap-1.5 px-2 text-sm font-medium text-accent-emerald-foreground">
            <Check className="h-3.5 w-3.5" />
            <span>{t("node.approved")}</span>
          </div>
        ) : (
          <button
            type="button"
            data-testid="assistant-approve-button"
            className={GHOST_PRIMARY_BUTTON}
            onClick={handleApprove}
          >
            <span>Approve</span>
            <Check className="h-3.5 w-3.5" />
          </button>
        )}
        <button
          type="button"
          data-testid="assistant-view-code-button"
          className={GHOST_SECONDARY_BUTTON}
          onClick={() => setIsViewCodeOpen(true)}
        >
          <span>{t("node.viewCode")}</span>
        </button>
      </div>

      {result.componentCode && (
        <CodeAreaModal
          value={result.componentCode}
          setValue={() => {}}
          nodeClass={undefined}
          setNodeClass={() => {}}
          dynamic={false}
          readonly={true}
          open={isViewCodeOpen}
          setOpen={setIsViewCodeOpen}
          size="medium"
        >
          <></>
        </CodeAreaModal>
      )}
    </div>
  );
}
