import { useEffect, useMemo, useState } from "react";
import { Check, FileText } from "lucide-react";
import type { AgenticResult } from "@/controllers/API/queries/agentic";
import { ViewCodeModal } from "./view-code-modal";

const APPROVED_DISPLAY_DURATION_MS = 3000;

interface FieldInfo {
  name: string;
  type: string;
}

function formatType(rawType: string): string {
  // e.g. "MessageTextInput" -> "Text", "IntInput" -> "Int", "StrInput" -> "Str"
  return rawType.replace(/Input$/, "").replace(/^Message/, "");
}

function parseComponentInfo(code: string | undefined) {
  if (!code) return { description: null, inputs: [] as FieldInfo[], outputs: [] as FieldInfo[] };

  // Extract description
  const descMatch = code.match(/description\s*=\s*"([^"]+)"/);
  const description = descMatch?.[1] || null;

  // Extract inputs with type (e.g. MessageTextInput, IntInput, etc.)
  const inputRegex = /(\w+Input)\(\s*(?:[^)]*?)display_name\s*=\s*"([^"]+)"/gs;
  const inputs: FieldInfo[] = [];
  let match;
  while ((match = inputRegex.exec(code)) !== null) {
    inputs.push({ name: match[2], type: formatType(match[1]) });
  }

  // Fallback: simpler pattern
  if (inputs.length === 0) {
    const simpleInputRegex = /(MessageTextInput|StrInput|IntInput|FloatInput|BoolInput|FileInput|DropdownInput|MultilineInput|SecretStrInput|HandleInput|DataInput)\s*\([^)]*display_name\s*=\s*"([^"]+)"/g;
    while ((match = simpleInputRegex.exec(code)) !== null) {
      inputs.push({ name: match[2], type: formatType(match[1]) });
    }
  }

  // Extract outputs: get display_name and method name, then resolve return type from method signature
  const outputRegex = /Output\(\s*(?:[^)]*?)display_name\s*=\s*"([^"]+)"(?:[^)]*?)method\s*=\s*"(\w+)"/gs;
  const outputs: FieldInfo[] = [];
  while ((match = outputRegex.exec(code)) !== null) {
    const methodName = match[2];
    // Look for the method's return type annotation: def method_name(self) -> ReturnType:
    const returnTypeRegex = new RegExp(`def\\s+${methodName}\\s*\\([^)]*\\)\\s*->\\s*(\\w+)`);
    const returnMatch = code.match(returnTypeRegex);
    const returnType = returnMatch?.[1] || "Message";
    outputs.push({ name: match[1], type: returnType });
  }

  // Fallback: outputs without method
  if (outputs.length === 0) {
    const simpleOutputRegex = /Output\(\s*(?:[^)]*?)display_name\s*=\s*"([^"]+)"/g;
    while ((match = simpleOutputRegex.exec(code)) !== null) {
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
    <div className="max-w-[80%] rounded-lg border border-border bg-muted/30 p-4">
      {/* Component header */}
      <div className="mb-3 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-[#0EA5E9]">
          <FileText className="h-4 w-4 text-white" />
        </div>
        <span className="text-sm font-semibold text-foreground">
          {componentName}
        </span>
      </div>

      {/* Component info */}
      <div className="mb-5 flex flex-col gap-3">
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
        {inputs.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-xs font-semibold text-foreground">Inputs</h4>
            <div className="flex flex-wrap gap-1.5 pl-1">
              {inputs.map((input) => (
                <span key={input.name} className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                  {input.name} <span className="text-muted-foreground/60">({input.type})</span>
                </span>
              ))}
            </div>
          </div>
        )}
        {outputs.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-xs font-semibold text-foreground">Outputs</h4>
            <div className="flex flex-wrap gap-1.5 pl-1">
              {outputs.map((output) => (
                <span key={output.name} className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                  {output.name} <span className="text-muted-foreground/60">({output.type})</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {showApproved ? (
          <div className="flex h-8 items-center gap-1.5 text-sm font-medium text-accent-emerald-foreground">
            <Check className="h-4 w-4" />
            <span>Approved</span>
          </div>
        ) : (
          <button
            type="button"
            className="h-8 rounded-[10px] bg-white px-4 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-100"
            onClick={handleApprove}
          >
            Approve
          </button>
        )}
        <button
          type="button"
          className="h-8 rounded-[10px] bg-zinc-700 px-4 text-sm font-medium text-white transition-colors hover:bg-zinc-600"
          onClick={() => setIsViewCodeOpen(true)}
        >
          View Code
        </button>
      </div>

      {result.componentCode && (
        <ViewCodeModal
          code={result.componentCode}
          open={isViewCodeOpen}
          onOpenChange={setIsViewCodeOpen}
        />
      )}
    </div>
  );
}
