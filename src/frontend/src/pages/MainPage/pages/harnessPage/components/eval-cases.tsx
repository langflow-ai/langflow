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
          className="space-y-4 rounded-lg border p-5"
        >
          <legend className="px-2 text-sm text-muted-foreground">
            {t("evaluations.caseNumber", { number: index + 1 })}
          </legend>
          <div className="flex items-end gap-4">
            <label className="flex-1 space-y-2 text-sm">
              {t("evaluations.name")}
              <Input
                value={item.name}
                maxLength={200}
                onChange={(event) =>
                  update(item.id, { name: event.target.value })
                }
              />
            </label>
            <Button
              variant="ghost"
              onClick={() =>
                onChange(cases.filter((row) => row.id !== item.id))
              }
            >
              {t("evaluations.remove")}
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <label className="space-y-2 text-sm">
              {t("evaluations.input")}
              <Textarea
                value={item.input}
                maxLength={16000}
                rows={4}
                onChange={(event) =>
                  update(item.id, { input: event.target.value })
                }
              />
            </label>
            <label className="space-y-2 text-sm">
              {t("evaluations.reference")}
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
              {t("evaluations.minimumScore")}
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={item.minimum_score}
                onChange={(event) =>
                  update(item.id, { minimum_score: event.target.valueAsNumber })
                }
              />
            </label>
            <label className="space-y-2 text-sm">
              {t("evaluations.latency")}
              <Input
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
            </label>
            <label className="space-y-2 text-sm">
              {t("evaluations.cost")}
              <Input
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
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-5 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
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
            <p className="text-sm text-warning-foreground">
              {t("evaluations.costUnavailable")}
            </p>
          )}
        </fieldset>
      ))}
    </section>
  );
}
