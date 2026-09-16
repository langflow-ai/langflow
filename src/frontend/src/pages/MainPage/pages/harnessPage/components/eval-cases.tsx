import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { EvalCase } from "@/controllers/API/queries/folders/use-eval-suite";

export const emptyCase = (): EvalCase => ({
  id: crypto.randomUUID(),
  name: "",
  input: "",
  reference: "",
  minimum_score: 1,
  require_sourced_artifact: true,
  require_supported_claims: true,
  expected_policy: "compliant",
  max_latency_ms: null,
  max_cost_usd: null,
});

const validScore = (value: number) =>
  Number.isFinite(value) && value >= 0 && value <= 1;
const validLatency = (value: number | null) =>
  value === null || (Number.isInteger(value) && value > 0 && value <= 3600000);
const validCost = (value: number | null) =>
  value === null || (Number.isFinite(value) && value > 0);
export const validEvalCase = (item: EvalCase) =>
  Boolean(
    item.name.trim() &&
      item.input.trim() &&
      validScore(item.minimum_score) &&
      validLatency(item.max_latency_ms) &&
      validCost(item.max_cost_usd),
  );

export function EvalCases({
  cases,
  onChange,
  disabled,
}: {
  cases: EvalCase[];
  onChange: (cases: EvalCase[]) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const [touched, setTouched] = useState<Set<string>>(() => new Set());
  const touch = (field: string) =>
    setTouched((previous) => new Set([...previous, field]));
  const update = (id: string, patch: Partial<EvalCase>) =>
    onChange(
      cases.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    );
  return (
    <section className="space-y-5" aria-label={t("evaluations.cases")}>
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          {t("evaluations.cases")}{" "}
          <span className="text-muted-foreground">{cases.length}/10</span>
        </h3>
        <Button
          variant="outline"
          disabled={disabled || cases.length >= 10}
          onClick={() => onChange([...cases, emptyCase()])}
        >
          {t("evaluations.addCase")}
        </Button>
      </div>
      {cases.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {t("evaluations.noCases")}
        </p>
      )}
      {cases.map((item, index) => (
        <fieldset
          disabled={disabled}
          key={item.id}
          className="min-w-0 space-y-5 rounded-xl bg-muted/40 p-5"
          aria-labelledby={`${item.id}-heading`}
        >
          <div className="flex items-center justify-between gap-4">
            <h4 id={`${item.id}-heading`} className="text-sm font-semibold">
              {t("evaluations.caseNumber", { number: index + 1 })}
            </h4>
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                onChange(cases.filter((row) => row.id !== item.id))
              }
            >
              {t("evaluations.remove")}
            </Button>
          </div>
          <label className="block space-y-2 text-sm">
            <span className="block">{t("evaluations.name")}</span>
            <Input
              aria-label={t("evaluations.name")}
              required
              aria-invalid={touched.has(`${item.id}-name`) && !item.name.trim()}
              aria-describedby={
                touched.has(`${item.id}-name`) && !item.name.trim()
                  ? `${item.id}-name-error`
                  : undefined
              }
              onBlur={() => touch(`${item.id}-name`)}
              value={item.name}
              maxLength={200}
              onChange={(event) =>
                update(item.id, { name: event.target.value })
              }
            />
            {touched.has(`${item.id}-name`) && !item.name.trim() && (
              <span
                id={`${item.id}-name-error`}
                className="block text-xs text-destructive"
              >
                {t("evaluations.nameRequired")}
              </span>
            )}
          </label>
          <div className="grid grid-cols-2 gap-4">
            <label className="space-y-2 text-sm">
              <span className="block">{t("evaluations.input")}</span>
              <Textarea
                aria-label={t("evaluations.input")}
                required
                aria-invalid={
                  touched.has(`${item.id}-input`) && !item.input.trim()
                }
                aria-describedby={
                  touched.has(`${item.id}-input`) && !item.input.trim()
                    ? `${item.id}-input-error`
                    : undefined
                }
                onBlur={() => touch(`${item.id}-input`)}
                value={item.input}
                maxLength={16000}
                rows={4}
                onChange={(event) =>
                  update(item.id, { input: event.target.value })
                }
              />
              {touched.has(`${item.id}-input`) && !item.input.trim() && (
                <span
                  id={`${item.id}-input-error`}
                  className="block text-xs text-destructive"
                >
                  {t("evaluations.inputRequired")}
                </span>
              )}
            </label>
            <label className="space-y-2 text-sm">
              <span className="block">{t("evaluations.reference")}</span>
              <Textarea
                value={item.reference}
                maxLength={16000}
                rows={4}
                onChange={(event) =>
                  update(item.id, { reference: event.target.value })
                }
              />
            </label>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <label className="space-y-2 text-sm">
              <span className="block min-h-10 leading-5">
                {t("evaluations.minimumScore")}
              </span>
              <Input
                aria-label={t("evaluations.minimumScore")}
                aria-invalid={!validScore(item.minimum_score)}
                aria-describedby={
                  !validScore(item.minimum_score)
                    ? `${item.id}-score-error`
                    : undefined
                }
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={
                  Number.isFinite(item.minimum_score) ? item.minimum_score : ""
                }
                onChange={(event) =>
                  update(item.id, { minimum_score: event.target.valueAsNumber })
                }
              />
              {!validScore(item.minimum_score) && (
                <span
                  id={`${item.id}-score-error`}
                  className="block text-xs text-destructive"
                >
                  {t("evaluations.scoreRange")}
                </span>
              )}
            </label>
            <label className="space-y-2 text-sm">
              <span className="block min-h-10 leading-5">
                {t("evaluations.latency")}
              </span>
              <Input
                aria-label={t("evaluations.latency")}
                aria-invalid={!validLatency(item.max_latency_ms)}
                aria-describedby={
                  !validLatency(item.max_latency_ms)
                    ? `${item.id}-latency-error`
                    : undefined
                }
                type="number"
                min={1}
                max={3600000}
                value={item.max_latency_ms ?? ""}
                onChange={(event) =>
                  update(item.id, {
                    max_latency_ms:
                      event.target.value === ""
                        ? null
                        : event.target.valueAsNumber,
                  })
                }
              />
              {!validLatency(item.max_latency_ms) && (
                <span
                  id={`${item.id}-latency-error`}
                  className="block text-xs text-destructive"
                >
                  {t("evaluations.latencyRange")}
                </span>
              )}
            </label>
            <label className="space-y-2 text-sm">
              <span className="block min-h-10 leading-5">
                {t("evaluations.cost")}
              </span>
              <Input
                aria-label={t("evaluations.cost")}
                aria-invalid={!validCost(item.max_cost_usd)}
                aria-describedby={
                  !validCost(item.max_cost_usd)
                    ? `${item.id}-cost-error`
                    : item.max_cost_usd !== null
                      ? `${item.id}-cost-warning`
                      : undefined
                }
                type="number"
                min={0.000001}
                step="any"
                value={item.max_cost_usd ?? ""}
                onChange={(event) =>
                  update(item.id, {
                    max_cost_usd:
                      event.target.value === ""
                        ? null
                        : event.target.valueAsNumber,
                  })
                }
              />
              {!validCost(item.max_cost_usd) && (
                <span
                  id={`${item.id}-cost-error`}
                  className="block text-xs text-destructive"
                >
                  {t("evaluations.costRange")}
                </span>
              )}
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-5 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={item.require_sourced_artifact}
                onChange={(event) =>
                  update(item.id, {
                    require_sourced_artifact: event.target.checked,
                  })
                }
              />
              {t("evaluations.requireArtifact")}
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={item.require_supported_claims}
                onChange={(event) =>
                  update(item.id, {
                    require_supported_claims: event.target.checked,
                  })
                }
              />
              {t("evaluations.requireClaims")}
            </label>
            <label className="flex items-center gap-2">
              {t("evaluations.policy")}
              <select
                className="rounded-md border bg-background p-2"
                value={item.expected_policy ?? ""}
                onChange={(event) =>
                  update(item.id, {
                    expected_policy: (event.target.value ||
                      null) as EvalCase["expected_policy"],
                  })
                }
              >
                <option value="">{t("evaluations.noPolicyCheck")}</option>
                <option value="compliant">{t("evaluations.compliant")}</option>
                <option value="violation">{t("evaluations.violation")}</option>
              </select>
            </label>
          </div>
          {item.max_cost_usd !== null && (
            <p
              id={`${item.id}-cost-warning`}
              className="rounded-lg bg-background p-3 text-sm text-foreground"
            >
              {t("evaluations.costUnavailable")}
            </p>
          )}
        </fieldset>
      ))}
    </section>
  );
}
