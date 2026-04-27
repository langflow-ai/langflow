import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Keep in sync with the backends actually registered by
 * ``lfx.base.knowledge_bases.backends`` (see ``backends/__init__.py``).
 *
 * In this phase only Chroma and OpenSearch are exposed in the UI.
 * MongoDB / Astra / Postgres are stubbed on the backend; their picker
 * options were dropped here so the dropdown only surfaces what's
 * actually wired through end-to-end. Restore the dropped options when
 * the corresponding backend stubs are reinstated.
 */
export const BACKEND_OPTIONS = [
  {
    value: "chroma",
    label: "Chroma (local)",
    description:
      "Zero-config local vector store. Good for desktop and single-user self-hosted.",
  },
  {
    value: "opensearch",
    label: "OpenSearch",
    description:
      "OpenSearch k-NN vector index for self-hosted or managed clusters.",
  },
] as const;

export type BackendValue = (typeof BACKEND_OPTIONS)[number]["value"];

export interface BackendPickerProps {
  /**
   * Controlled backend identifier. Use ``"chroma"`` as the default.
   */
  value: BackendValue;
  onValueChange: (value: BackendValue) => void;
  /**
   * Backend-specific config. Keys depend on the selected backend.
   * See the full schema in ``use-create-knowledge-base.ts``.
   */
  config: Record<string, string>;
  onConfigChange: (config: Record<string, string>) => void;
  /**
   * When true (editing an existing KB), the picker is read-only.
   * Backend choice is immutable after a KB is created because it
   * determines where the vectors live.
   */
  disabled?: boolean;
}

/**
 * Vector-store backend picker for the KB creation dialog.
 *
 * Renders a dropdown to choose between the registered backends
 * (Chroma / OpenSearch) plus a compact per-backend config form. Every
 * credential field accepts a *variable name*, not a raw secret — the
 * actual value lives in Langflow's variable settings.
 */
export function BackendPicker({
  value,
  onValueChange,
  config,
  onConfigChange,
  disabled,
}: BackendPickerProps) {
  const setField = (key: string, fieldValue: string) => {
    onConfigChange({ ...config, [key]: fieldValue });
  };

  const activeOption =
    BACKEND_OPTIONS.find((o) => o.value === value) ?? BACKEND_OPTIONS[0];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        <Label className="flex items-center gap-1 text-sm font-medium">
          Vector Store Backend
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="cursor-help">
                  <ForwardedIconComponent
                    name="Info"
                    className="h-3.5 w-3.5 text-muted-foreground"
                  />
                </span>
              </TooltipTrigger>
              <TooltipContent className="max-w-[300px]">
                Where this KB's vectors live. Chroma stores them on disk next to
                Langflow. OpenSearch sends them to an external cluster you've
                configured. The choice is immutable after creation.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </Label>
        <Select
          value={value}
          onValueChange={(next) => onValueChange(next as BackendValue)}
          disabled={disabled}
        >
          <SelectTrigger data-testid="kb-backend-picker">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {BACKEND_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground">
          {activeOption.description}
        </span>
      </div>

      {value === "opensearch" && (
        <BackendConfigSection>
          <FieldInput
            label="Cluster URL variable"
            placeholder="OPENSEARCH_URL"
            value={config.url_variable ?? ""}
            onChange={(v) => setField("url_variable", v)}
            disabled={disabled}
          />
          <FieldInput
            label="Username variable"
            placeholder="OPENSEARCH_USERNAME"
            value={config.username_variable ?? ""}
            onChange={(v) => setField("username_variable", v)}
            disabled={disabled}
          />
          <FieldInput
            label="Password variable"
            placeholder="OPENSEARCH_PASSWORD"
            value={config.password_variable ?? ""}
            onChange={(v) => setField("password_variable", v)}
            disabled={disabled}
          />
          <FieldInput
            label="Index name"
            placeholder="my_kb_index"
            value={config.index_name ?? ""}
            onChange={(v) => setField("index_name", v)}
            required
            disabled={disabled}
          />
          <FieldInput
            label="Vector field"
            placeholder="vector_field"
            value={config.vector_field ?? ""}
            onChange={(v) => setField("vector_field", v)}
            disabled={disabled}
          />
          <FieldInput
            label="Text field"
            placeholder="text"
            value={config.text_field ?? ""}
            onChange={(v) => setField("text_field", v)}
            disabled={disabled}
          />
        </BackendConfigSection>
      )}
    </div>
  );
}

function BackendConfigSection({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-border bg-muted/30 p-3">
      <span className="text-xs font-medium text-muted-foreground">
        Backend configuration
      </span>
      <span className="text-[11px] text-muted-foreground">
        Credential fields accept Langflow variable <em>names</em>. Store the
        actual secrets via the provider settings page.
      </span>
      <div className="grid grid-cols-1 gap-2">{children}</div>
    </div>
  );
}

function FieldInput({
  label,
  placeholder,
  value,
  onChange,
  required,
  disabled,
}: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  disabled?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">
        {label}
        {required ? " *" : ""}
      </span>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
      />
    </label>
  );
}
