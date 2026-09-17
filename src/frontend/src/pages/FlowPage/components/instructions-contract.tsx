import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useFlowStore from "@/stores/flowStore";

type Validation = { valid: boolean; outputs: unknown[] };

/** Inspect the live graph using the same static contract resolver as the harness picker. */
export function InstructionsContract() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const flow = useFlowStore((state) => state.currentFlow);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const marker = (
    flow?.data as { harness_contract?: { slot?: string } } | undefined
  )?.harness_contract;
  const active =
    params.get("harnessField") === "system_prompt" ||
    marker?.slot === "SystemPromptBuilder";
  const projectId = active ? flow?.folder_id : undefined;
  // Selection and layout do not affect the output contract or trigger validation requests.
  const definition = useMemo(
    () =>
      JSON.stringify({
        nodes: nodes.map(({ id, data }) => ({ id, data })),
        edges,
      }),
    [nodes, edges],
  );
  const [attempt, setAttempt] = useState(0);
  const validationKey = `${flow?.id}:${projectId}:${definition}:${attempt}`;
  const [result, setResult] = useState<{
    key: string;
    validation?: Validation;
    error?: boolean;
  }>();
  useEffect(() => {
    if (!projectId) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void api
        .post<Validation>(
          `${getURL("PROJECTS")}/${projectId}/flow-outputs/validate`,
          { data: JSON.parse(definition) },
          { signal: controller.signal },
        )
        .then(({ data }) => {
          if (!controller.signal.aborted)
            setResult({ key: validationKey, validation: data });
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setResult({ key: validationKey, error: true });
        });
    }, 400);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [projectId, definition, validationKey]);
  if (!projectId) return null;
  const current = result?.key === validationKey ? result : undefined;
  const status = !current
    ? "checkingInstructionsContract"
    : current.error
      ? "instructionsContractUnavailable"
      : current.validation?.valid
        ? "instructionsContractReady"
        : "instructionsContractInvalid";
  return (
    <aside
      aria-label={t("harness.instructionsContract")}
      className="max-h-[45%] shrink-0 overflow-y-auto border-b border-border bg-background px-4 py-3"
      data-testid="instructions-contract"
    >
      <div className="flex flex-col items-start justify-between gap-x-4 gap-y-2 sm:flex-row">
        <details className="w-full min-w-0 flex-1 sm:w-auto">
          <summary className="cursor-pointer text-sm font-medium">
            {t("harness.instructionsContract")}
            <span
              role="status"
              className={`ml-2 font-normal ${current?.error || current?.validation?.valid === false ? "text-destructive" : "text-muted-foreground"}`}
            >
              {t(`harness.${status}`)}
            </span>
          </summary>
          <div className="mt-2 max-w-2xl space-y-1 text-sm text-muted-foreground">
            <p>{t("harness.instructionsContractHelp")}</p>
            {current?.error && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setAttempt((value) => value + 1)}
              >
                {t("harness.retryFlows")}
              </Button>
            )}
            {current?.validation?.valid === false && (
              <p>{t("harness.instructionsContractFix")}</p>
            )}
            <p>{t("harness.instructionsContractReview")}</p>
          </div>
        </details>
        <Link
          to={`/all/folder/${projectId}?tab=harness&field=system_prompt`}
          className="shrink-0 text-sm text-primary underline underline-offset-4"
        >
          {t("harness.returnToInstructions")}
        </Link>
      </div>
    </aside>
  );
}
