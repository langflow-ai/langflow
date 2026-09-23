import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { useLocalToolDefinitions } from "@/controllers/API/queries/folders/use-local-tool-definitions";
import type { LocalToolBinding } from "@/pages/MainPage/entities";
import { FlowBindingDependencies } from "./flow-binding-dependencies";

export const sameLocalToolDefinition = (
  a?: LocalToolBinding,
  b?: LocalToolBinding,
) => {
  if (!a || !b) return false;
  const definition = (binding: LocalToolBinding) =>
    [binding, ...(binding.dependencies ?? [])]
      .map(({ flow_id, name, description, revision }) => [
        flow_id,
        name,
        description ?? "",
        revision,
      ])
      .sort(([first], [second]) => first.localeCompare(second));
  return JSON.stringify(definition(a)) === JSON.stringify(definition(b));
};

export function LocalToolReview({
  projectId,
  selected,
  value = {},
  saved = {},
  disabled,
  onChange,
  onOpen,
}: {
  projectId: string;
  selected: string[];
  value?: Record<string, LocalToolBinding>;
  saved?: Record<string, LocalToolBinding>;
  disabled: boolean;
  onChange: (value: Record<string, LocalToolBinding>) => void;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  const choices = useLocalToolDefinitions(
    { projectId },
    { enabled: selected.length > 0 },
  );
  if (!selected.length) return null;
  if (choices.isLoading)
    return (
      <p className="text-xs text-muted-foreground">
        {t("harness.loadingFlows")}
      </p>
    );
  if (choices.isError)
    return (
      <div role="alert" className="space-y-2 text-sm">
        <p>{t("harness.flowsLoadFailed")}</p>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => void choices.refetch()}
        >
          {t("harness.retryFlows")}
        </Button>
      </div>
    );
  return (
    <div className="mt-3 space-y-3" data-testid="local-tool-review">
      {selected.map((id) => {
        const current = choices.data?.find((item) => item.flow_id === id);
        const reviewed = value[id];
        const changed =
          !!reviewed &&
          !!current &&
          !sameLocalToolDefinition(reviewed, current);
        const records = current
          ? [current, ...(current.dependencies ?? [])]
          : reviewed
            ? [reviewed, ...(reviewed.dependencies ?? [])]
            : [];
        return (
          <div key={id} className="space-y-2">
            {!current && (
              <p role="status" className="text-xs text-destructive">
                {reviewed?.name ?? id}: {t("harness.boundFlowUnavailable")}
              </p>
            )}
            {current && reviewed && (
              <div className="flex items-center justify-between gap-3 text-xs">
                <p
                  className={
                    changed ? "text-destructive" : "text-muted-foreground"
                  }
                >
                  {t(
                    changed
                      ? "toolPacks.changed"
                      : sameLocalToolDefinition(saved[id], reviewed)
                        ? "toolPacks.current"
                        : "toolPacks.pending",
                  )}
                </p>
                {changed && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={disabled}
                    onClick={() => onChange({ ...value, [id]: current })}
                  >
                    {t("harness.updateBinding")}
                  </Button>
                )}
              </div>
            )}
            <FlowBindingDependencies
              title={current?.name ?? reviewed?.name}
              dependencies={records}
              reviewed={
                current && reviewed
                  ? [reviewed, ...(reviewed.dependencies ?? [])]
                  : undefined
              }
              onOpen={onOpen}
            />
          </div>
        );
      })}
    </div>
  );
}
