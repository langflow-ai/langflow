import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { RunEstimate } from "@/controllers/API/queries/evals/types";
import {
  formatRange,
  formatTokenCount,
  formatUsd,
} from "@/pages/MainPage/pages/evalsPage/utils/format";
import BaseModal from "../baseModal";

interface ConfirmRunDialogProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  /** Missing when the estimate failed: the dialog then says the cost is unknown. */
  estimate?: RunEstimate;
  loading: boolean;
  onConfirm: () => void;
}

function EstimateDetails({ estimate }: { estimate: RunEstimate }) {
  const { t } = useTranslation();
  const cost =
    estimate.cost_low === null || estimate.cost_high === null
      ? t("evals.estimate.costUnknown")
      : formatRange(
          formatUsd(estimate.cost_low),
          formatUsd(estimate.cost_high),
        );
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg border px-4 py-3 text-sm">
      <dt className="text-muted-foreground">{t("evals.confirm.rows")}</dt>
      <dd className="text-right tabular-nums">{estimate.items}</dd>
      <dt className="text-muted-foreground">{t("evals.confirm.calls")}</dt>
      <dd className="text-right tabular-nums">{estimate.llm_calls}</dd>
      <dt className="text-muted-foreground">{t("evals.confirm.tokens")}</dt>
      <dd className="text-right tabular-nums">
        {formatRange(
          formatTokenCount(estimate.tokens_low),
          formatTokenCount(estimate.tokens_high),
        )}
      </dd>
      <dt className="text-muted-foreground">{t("evals.confirm.cost")}</dt>
      <dd
        className="text-right font-semibold tabular-nums"
        data-testid="confirm-run-cost"
      >
        {cost}
      </dd>
    </dl>
  );
}

/** The last stop before a run spends real tokens: states the calls and the cost range. */
export default function ConfirmRunDialog({
  open,
  setOpen,
  estimate,
  loading,
  onConfirm,
}: ConfirmRunDialogProps) {
  const { t } = useTranslation();
  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="small-update"
      onSubmit={onConfirm}
    >
      <BaseModal.Header description={t("evals.confirm.description")}>
        <ForwardedIconComponent name="Coins" className="mr-2 h-4 w-4" />
        {t("evals.confirm.title")}
      </BaseModal.Header>
      <BaseModal.Content>
        {estimate ? (
          <EstimateDetails estimate={estimate} />
        ) : (
          <p
            className="rounded-lg border px-4 py-3 text-sm"
            data-testid="confirm-run-no-estimate"
          >
            {t("evals.confirm.noEstimate")}
          </p>
        )}
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("evals.confirm.submit"),
          loading,
          dataTestId: "confirm-run-submit",
        }}
      />
    </BaseModal>
  );
}
