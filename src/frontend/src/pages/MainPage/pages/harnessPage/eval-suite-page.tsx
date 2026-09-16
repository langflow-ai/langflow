import "./harness-form.css";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { api } from "@/controllers/API/api";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import {
  type EvalConfig,
  evalURL,
  useEvalRuns,
  useEvalSuite,
  useRunEvalSuite,
} from "@/controllers/API/queries/folders/use-eval-suite";
import { usePatchFolders } from "@/controllers/API/queries/folders/use-patch-folders";
import type { FlowType } from "@/types/flow";
import { EvalCases, validEvalCase } from "./components/eval-cases";
import { EvalRuns } from "./components/eval-runs";
import { bindingOf, outputKey, sameBindingDefinition } from "./flow-binding";

function errorDetail(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

export default function EvalSuitePage({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const query = useEvalSuite(projectId);
  const run = useRunEvalSuite(projectId);
  const history = useEvalRuns(projectId, run.isPending);
  const save = usePatchFolders();
  const createFlow = usePostAddFlow();
  const [draft, setDraft] = useState<EvalConfig | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    generation.current += 1;
    return () => {
      generation.current += 1;
    };
  }, [projectId]);
  // A lost response is not permission to replay side effects. Keep the submission
  // ID visible and require checking persisted history before starting another run.
  const [uncertainRun, setUncertainRun] = useState<string | null>(null);
  const config = draft ?? query.data?.config;
  const dirty =
    draft !== null &&
    JSON.stringify(draft) !== JSON.stringify(query.data?.config);
  const busy = run.isPending || save.isPending || saving || creating;
  const validCases = config?.cases.every(validEvalCase);

  if (query.isLoading)
    return (
      <p className="p-8 text-muted-foreground">{t("evaluations.loading")}</p>
    );
  if (!config || !query.data)
    return (
      <div className="p-8">
        <p role="alert">{t("evaluations.loadError")}</p>
        <Button variant="outline" onClick={() => void query.refetch()}>
          {t("evaluations.refresh")}
        </Button>
      </div>
    );
  const change = (patch: Partial<EvalConfig>) =>
    setDraft({ ...config, ...patch });
  const saveSuite = async () => {
    setSaving(true);
    setError("");
    try {
      await save.mutateAsync({
        folderId: projectId,
        data: { project_config: config },
      });
      const refreshed = await query.refetch();
      if (refreshed.isError || !refreshed.data) {
        setError(t("evaluations.refreshAfterSaveError"));
      } else {
        setDraft(null);
      }
    } catch (cause) {
      setError(errorDetail(cause, t("evaluations.saveError")));
    } finally {
      setSaving(false);
    }
  };
  const runSuite = async () => {
    const runId = crypto.randomUUID();
    setError("");
    try {
      await run.mutateAsync({
        run_id: runId,
        expected_revision: query.data.revision,
        expected_candidate_digest: config.candidate_digest!,
      });
    } catch (cause) {
      setUncertainRun(runId);
      setError(errorDetail(cause, t("evaluations.runError")));
    }
  };
  const createScorer = async () => {
    const started = generation.current;
    setCreating(true);
    setError("");
    try {
      const { data } = await api.post<FlowType>(
        `${evalURL(projectId)}/scorer-baseline`,
      );
      if (generation.current !== started) return;
      const flow = await createFlow.mutateAsync({
        ...data,
        data: data.data!,
        folder_id: projectId,
        is_component: false,
        endpoint_name: undefined,
        icon: undefined,
        gradient: undefined,
        tags: undefined,
        mcp_enabled: false,
      });
      if (generation.current === started) navigate(`/flow/${flow.id}`);
    } catch (cause) {
      if (generation.current === started)
        setError(errorDetail(cause, t("evaluations.createError")));
    } finally {
      if (generation.current === started) setCreating(false);
    }
  };
  const targetKey = `${config.workflow_id}:${config.candidate_digest}`;
  const mounted = query.data.targets.some(
    (item) => `${item.workflow_id}:${item.candidate_digest}` === targetKey,
  );
  const scorerKey = config.scorer ? outputKey(config.scorer) : "";
  const currentScorer = query.data.scorers.find(
    (item) => outputKey(item) === scorerKey,
  );
  const scorerChanged =
    config.scorer &&
    currentScorer &&
    !sameBindingDefinition(config.scorer, currentScorer);
  return (
    <div className="harness-form mx-auto min-w-0 w-full max-w-6xl space-y-8">
      <header className="sticky top-0 z-10 -mt-4 flex items-start justify-between gap-6 border-b bg-background py-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">
            {t("evaluations.title")}
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            {t("evaluations.description")}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button
            variant="outline"
            disabled={busy || !dirty || !validCases}
            onClick={() => void saveSuite()}
          >
            {t("evaluations.save")}
          </Button>
          <Button
            disabled={
              busy ||
              dirty ||
              !validCases ||
              !mounted ||
              !config.scorer ||
              !config.cases.length ||
              !!uncertainRun
            }
            onClick={() => void runSuite()}
          >
            {t(run.isPending ? "evaluations.running" : "evaluations.run")}
          </Button>
        </div>
      </header>
      <p className="text-xs text-muted-foreground">
        {t("evaluations.limits")}
        {dirty && ` ${t("evaluations.unsaved")}`}
      </p>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {uncertainRun && (
        <div className="rounded-md border p-4 text-sm">
          <p>
            {t("evaluations.checkSubmission")} <code>{uncertainRun}</code>
          </p>
          <Button
            variant="outline"
            className="mt-3"
            onClick={() => {
              void history.refetch();
            }}
          >
            {t("evaluations.refresh")}
          </Button>
          <Button
            variant="ghost"
            className="ml-2"
            onClick={() => setUncertainRun(null)}
          >
            {t("evaluations.reviewedSubmission")}
          </Button>
        </div>
      )}
      <div className="grid grid-cols-2 gap-8">
        <div className="space-y-3">
          <label className="block space-y-2 text-sm font-medium">
            <span className="block">{t("evaluations.candidate")}</span>
            <select
              className="w-full rounded-md border bg-background p-2 font-normal"
              disabled={busy}
              value={config.workflow_id ? targetKey : ""}
              onChange={(event) => {
                const target = query.data.targets.find(
                  (item) =>
                    `${item.workflow_id}:${item.candidate_digest}` ===
                    event.target.value,
                );
                if (target)
                  change({
                    workflow_id: target.workflow_id,
                    candidate_digest: target.candidate_digest,
                  });
              }}
            >
              <option value="" disabled>
                {t("evaluations.chooseCandidate")}
              </option>
              {config.workflow_id && !mounted && (
                <option value={targetKey}>
                  {t("evaluations.unavailableCandidate")}
                </option>
              )}
              {query.data.targets.map((item) => (
                <option
                  key={`${item.workflow_id}:${item.candidate_digest}`}
                  value={`${item.workflow_id}:${item.candidate_digest}`}
                >
                  {item.name} · {item.candidate_digest.slice(0, 12)}
                </option>
              ))}
            </select>
          </label>
          {config.candidate_digest && (
            <p className="break-all font-mono text-xs text-muted-foreground">
              {config.candidate_digest}
            </p>
          )}
          {!query.data.targets.length && (
            <p className="text-sm text-muted-foreground">
              {t("evaluations.noCandidates")}
            </p>
          )}
        </div>
        <div className="space-y-3">
          <label className="block space-y-2 text-sm font-medium">
            <span className="block">{t("evaluations.scorer")}</span>
            <select
              className="w-full rounded-md border bg-background p-2 font-normal"
              disabled={busy}
              value={scorerKey}
              onChange={(event) => {
                const choice = query.data.scorers.find(
                  (item) => outputKey(item) === event.target.value,
                );
                if (choice) {
                  change({ scorer: bindingOf(choice) });
                }
              }}
            >
              <option value="" disabled>
                {t("evaluations.chooseScorer")}
              </option>
              {config.scorer && !currentScorer && (
                <option value={scorerKey}>
                  {t("evaluations.savedScorer")}
                </option>
              )}
              {query.data.scorers.map((item) => (
                <option key={outputKey(item)} value={outputKey(item)}>
                  {item.flow_name} · {item.display_name} ·{" "}
                  {(outputKey(item) === scorerKey && config.scorer
                    ? config.scorer.revision
                    : item.revision
                  ).slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          {scorerChanged && (
            <div className="space-y-3 rounded-xl bg-muted/40 p-4">
              <p className="text-sm text-muted-foreground">
                {t("evaluations.scorerChanged")}
              </p>
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => change({ scorer: bindingOf(currentScorer) })}
              >
                {t("evaluations.useUpdatedScorer")}
              </Button>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            {t("evaluations.scorerHelp")}
          </p>
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              disabled={busy || dirty}
              onClick={() => void createScorer()}
            >
              {t("evaluations.createScorer")}
            </Button>
            {config.scorer && !dirty && (
              <Link
                className="text-sm underline"
                to={`/flow/${config.scorer.flow_id}`}
              >
                {t("evaluations.openScorer")}
              </Link>
            )}
          </div>
        </div>
      </div>
      {history.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {t("evaluations.historyError")}
        </p>
      ) : (
        <EvalRuns projectId={projectId} runs={history.data ?? []} />
      )}
      <EvalCases
        cases={config.cases}
        disabled={busy}
        onChange={(cases) => change({ cases })}
      />
    </div>
  );
}
