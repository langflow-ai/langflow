import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { FlowType } from "@/types/flow";
import { cn } from "@/utils/utils";

interface HarnessSummaryProps {
  /** The project type's own presentation, so this panel never hardcodes one type. */
  displayName: string;
  icon?: string;
  /** The model value as the model widget stores it: a list holding the picked model. */
  model?: unknown;
  toolFlows: FlowType[];
  /** Every other field the form holds, already formatted for reading. */
  details: { name: string; label: string; value: string }[];
  className?: string;
  agentFlow?: FlowType;
}

const Eyebrow = ({ children }: { children: React.ReactNode }) => (
  <span className="text-xs font-medium text-muted-foreground">{children}</span>
);

const modelLabel = (model: unknown): string | null => {
  const picked = Array.isArray(model) ? model[0] : model;
  if (!picked) return null;
  if (typeof picked === "string") return picked || null;
  const named = picked as { name?: string; provider?: string };
  if (!named.name) return null;
  return named.provider ? `${named.name} · ${named.provider}` : named.name;
};

/**
 * What the harness adds up to.
 *
 * A form is a list of fields; an agent is one thing. This reads the values back as the assembled
 * agent, so the person building it can see what they have made without re-reading every field.
 */
export const HarnessSummary = ({
  displayName,
  icon,
  model,
  toolFlows,
  details,
  className,
  agentFlow,
}: HarnessSummaryProps) => {
  const { t } = useTranslation();
  const pickedModel = modelLabel(model);

  return (
    <aside
      data-testid="harness-summary"
      aria-label={t("harness.summaryTitle")}
      className={cn(
        "flex h-fit min-w-0 flex-col gap-5 rounded-lg border border-border bg-background p-4",
        className,
      )}
    >
      <div className="flex shrink-0 items-center gap-2">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
          <ForwardedIconComponent
            name={icon || "Bot"}
            aria-hidden="true"
            className="h-4 w-4 text-foreground"
          />
        </div>
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-semibold">{displayName}</span>
          <span className="text-xs font-normal text-muted-foreground">
            {t("harness.summaryTitle")}
          </span>
        </div>
      </div>

      {agentFlow && (
        <div className="flex min-w-0 flex-col gap-1.5 border-b border-border pb-4">
          <Eyebrow>{t("harness.appliesTo")}</Eyebrow>
          <a
            href={`/flow/${agentFlow.id}`}
            className="flex min-w-0 items-center gap-2 rounded-sm text-sm font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="truncate">{agentFlow.name}</span>
            <ForwardedIconComponent
              name="ArrowUpRight"
              aria-hidden="true"
              className="h-3.5 w-3.5 shrink-0"
            />
          </a>
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <Eyebrow>{t("harness.summaryModel")}</Eyebrow>
        {pickedModel ? (
          <span
            className="truncate text-sm font-medium"
            data-testid="harness-summary-model"
          >
            {pickedModel}
          </span>
        ) : (
          <span
            className="text-sm text-muted-foreground"
            data-testid="harness-summary-model-empty"
          >
            {t("harness.summaryModelEmpty")}
          </span>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-2">
          <Eyebrow>{t("harness.summaryTools")}</Eyebrow>
          {toolFlows.length > 0 && (
            <Badge variant="secondaryStatic" size="tag">
              {toolFlows.length}
            </Badge>
          )}
        </div>
        {toolFlows.length === 0 ? (
          <span
            className="text-sm text-muted-foreground"
            data-testid="harness-summary-tools-empty"
          >
            {t("harness.summaryToolsEmpty")}
          </span>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {toolFlows.map((flow) => (
              <li
                key={flow.id}
                className="flex items-center gap-2"
                data-testid={`harness-summary-tool-${flow.id}`}
              >
                <ForwardedIconComponent
                  name={flow.icon || "Workflow"}
                  aria-hidden="true"
                  className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                />
                <span className="truncate text-sm font-medium">
                  {flow.name}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {details.length > 0 && (
        <div className="flex flex-col border-t border-border pt-2">
          {details.map((detail) => (
            <div
              key={detail.name}
              className="flex items-center justify-between gap-3 py-1.5"
            >
              <span className="text-sm text-muted-foreground">
                {detail.label}
              </span>
              <span
                className="truncate text-sm font-medium"
                data-testid={`harness-summary-detail-${detail.name}`}
              >
                {detail.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
};

export default HarnessSummary;
