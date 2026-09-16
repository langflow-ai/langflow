import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { FlowType } from "@/types/flow";

export const agentCandidates = (flows: FlowType[]) =>
  flows.filter(
    (flow) =>
      !flow.is_component &&
      flow.data?.nodes?.filter((node) => node.data?.type === "Agent").length ===
        1,
  );

export const defaultAgent = (flows: FlowType[]) => {
  const candidates = agentCandidates(flows);
  const marked = candidates.filter((flow) => flow.flow_type === "agent");
  const choices = marked.length ? marked : candidates;
  return choices.length === 1 ? choices[0] : undefined;
};

export function AgentFlowPicker({
  flows,
  value,
  isLoading,
  disabled,
  onChange,
}: {
  flows: FlowType[];
  value?: string;
  isLoading: boolean;
  disabled: boolean;
  onChange: (id: string) => void;
}) {
  const { t } = useTranslation();
  const candidates = agentCandidates(flows);
  return (
    <section
      className="flex min-w-0 flex-col gap-4 border-b border-border/60 pb-8"
      data-testid="harness-agent-section"
    >
      <div>
        <h2 className="text-base font-semibold" id="harness-agent-label">
          {t("harness.agentFlow")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("harness.agentFlowHelp")}
        </p>
      </div>
      <Select
        value={value ?? ""}
        onValueChange={onChange}
        disabled={disabled || isLoading || !candidates.length}
      >
        <SelectTrigger
          aria-labelledby="harness-agent-label"
          data-testid="harness-agent-picker"
          className="w-full min-w-0"
        >
          <SelectValue
            placeholder={t(
              isLoading ? "harness.loadingFlows" : "harness.chooseAgent",
            )}
          />
        </SelectTrigger>
        <SelectContent>
          {candidates.map((flow) => (
            <SelectItem key={flow.id} value={flow.id}>
              {flow.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {!isLoading && !candidates.length && (
        <p className="text-sm text-muted-foreground">{t("harness.noAgent")}</p>
      )}
      {!isLoading && candidates.length > 1 && !value && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("harness.ambiguousAgent")}
        </p>
      )}
      {!isLoading && value && !candidates.some((flow) => flow.id === value) && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("harness.agentUnavailable")}
        </p>
      )}
      {flows.find((flow) => flow.id === value)?.locked && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("harness.agentLocked")}
        </p>
      )}
    </section>
  );
}
