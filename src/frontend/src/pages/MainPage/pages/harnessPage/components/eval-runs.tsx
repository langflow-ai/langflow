import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  comparableRuns,
  type EvalRun,
} from "@/controllers/API/queries/folders/use-eval-suite";

import { ProjectChoiceField } from "./project-choice-field";

export function EvalRuns({ runs }: { runs: EvalRun[] }) {
  const { t } = useTranslation();
  const [selectedId, setSelectedId] = useState("");
  const [baselineId, setBaselineId] = useState("");
  const selected = runs.find((run) => run.id === selectedId) ?? runs[0];
  const baseline = runs.find((run) => run.id === baselineId);
  const comparable = selected && baseline && comparableRuns(selected, baseline);
  const label = (run: EvalRun) =>
    `${new Date(run.created_at).toLocaleString()} · ${run.candidate_digest.slice(0, 12)} · ${t(run.passed ? "evaluations.passed" : run.result?.complete && run.status === "completed" ? "evaluations.failed" : "evaluations.incomplete")}`;
  return (
    <section
      className="space-y-4 border-t pt-6"
      aria-label={t("evaluations.runs")}
    >
      <h3 className="text-lg font-semibold">{t("evaluations.runs")}</h3>
      {!selected ? (
        <p className="text-sm text-muted-foreground">
          {t("evaluations.noRuns")}
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <label className="space-y-2">
              <span className="block">{t("evaluations.selectedRun")}</span>
              <ProjectChoiceField
                name="eval-run"
                label={t("evaluations.selectedRun")}
                value={selected.id}
                onChange={setSelectedId}
                options={Object.fromEntries(
                  runs.map((run) => [run.id, label(run)]),
                )}
              />
            </label>
            <label className="space-y-2">
              <span className="block">{t("evaluations.compareWith")}</span>
              <ProjectChoiceField
                name="eval-comparison"
                label={t("evaluations.compareWith")}
                value={baselineId || "none"}
                onChange={(value) =>
                  setBaselineId(value === "none" ? "" : value)
                }
                options={{
                  none: t("evaluations.noComparison"),
                  ...Object.fromEntries(
                    runs
                      .filter((run) => run.id !== selected.id)
                      .map((run) => [run.id, label(run)]),
                  ),
                }}
              />
            </label>
          </div>
          {baseline && !comparable && (
            <p role="status" className="text-sm text-muted-foreground">
              {t("evaluations.comparisonMismatch")}
            </p>
          )}
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <dt>{t("evaluations.candidate")}</dt>
            <dd className="break-all font-mono">{selected.candidate_digest}</dd>
            <dt>{t("evaluations.scorer")}</dt>
            <dd className="break-all font-mono">{selected.scorer_digest}</dd>
            <dt>{t("evaluations.runId")}</dt>
            <dd className="font-mono">{selected.id}</dd>
          </dl>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted">
                <tr>
                  {["case", "outcome", "score", "elapsed", "comparison"].map(
                    (key) => (
                      <th className="p-3 font-medium" key={key}>
                        {t(`evaluations.${key}`)}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {selected.result?.cases.map((item) => {
                  const original = selected.result?.suite.cases.find(
                    (entry) => entry.id === item.case_id,
                  );
                  const prior = comparable
                    ? baseline.result?.cases.find(
                        (entry) => entry.case_id === item.case_id,
                      )
                    : undefined;
                  const delta =
                    item.verdict && prior?.verdict
                      ? item.verdict.score - prior.verdict.score
                      : null;
                  return (
                    <tr className="border-t align-top" key={item.case_id}>
                      <td className="p-3">{original?.name ?? item.case_id}</td>
                      <td className="p-3">
                        <span
                          className={
                            item.passed
                              ? "text-success-foreground"
                              : "text-destructive"
                          }
                        >
                          {t(
                            item.passed
                              ? "evaluations.passed"
                              : "evaluations.failed",
                          )}
                        </span>
                        <ul className="mt-1 text-xs text-muted-foreground">
                          {item.failures.map((failure) => (
                            <li key={failure}>
                              {t(`evaluations.failures.${failure}`, {
                                defaultValue: failure.replaceAll("_", " "),
                              })}
                            </li>
                          ))}
                        </ul>
                        {item.verdict && (
                          <p className="mt-2 max-w-xl">{item.verdict.reason}</p>
                        )}
                        <details className="mt-2">
                          <summary className="cursor-pointer text-muted-foreground">
                            {t("evaluations.evidence")}
                          </summary>
                          <pre className="mt-2 max-h-80 max-w-xl overflow-auto whitespace-pre-wrap break-all rounded bg-muted p-3 text-xs">
                            {JSON.stringify(
                              { case: original, ...item },
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      </td>
                      <td className="p-3 tabular-nums">
                        {item.verdict?.score ?? "—"}
                      </td>
                      <td className="p-3 tabular-nums">
                        {item.latency_ms === null
                          ? "—"
                          : `${item.latency_ms} ms`}
                      </td>
                      <td className="p-3 tabular-nums">
                        {delta === null
                          ? "—"
                          : `${delta > 0 ? "+" : ""}${delta.toFixed(2)}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {(!selected.result?.complete || selected.status !== "completed") && (
            <p role="status" className="text-sm text-muted-foreground">
              {t("evaluations.incompleteRun", { status: selected.status })}
            </p>
          )}
        </>
      )}
    </section>
  );
}
