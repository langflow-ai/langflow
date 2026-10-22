import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { Button } from "@/components/ui/button";

/** Loading affordance shown while providers/enabled-models are being fetched. */
export function ModelInputLoadingButton(): JSX.Element {
  const { t } = useTranslation();
  return (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
      disabled
    >
      <LoadingTextComponent text={t("modelInput.loadingModels")} />
    </Button>
  );
}

/** A picker whose models failed to load; pressing it loads them again. */
export function ModelInputErrorButton({
  label,
  onRetry,
}: {
  label: string;
  onRetry: () => void;
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
      data-testid="model-input-load-failed"
      aria-label={`${label} (${t("common.retry")})`}
      onClick={onRetry}
    >
      <span className="flex items-center gap-2 truncate text-left">
        <ForwardedIconComponent
          name="AlertTriangle"
          aria-hidden="true"
          className="h-3.5 w-3.5 shrink-0 text-status-yellow"
        />
        <span className="truncate" title={label}>
          {label}
        </span>
      </span>
      <ForwardedIconComponent
        name="RotateCw"
        aria-hidden="true"
        className="h-3.5 w-3.5"
      />
    </Button>
  );
}

/** A picker that can't offer models and has nothing to press, read out as a notice. */
export function ModelInputNotice({
  label,
  testId,
}: {
  label: string;
  testId: string;
}): JSX.Element {
  return (
    <div
      role="status"
      data-testid={testId}
      className="flex w-full items-center gap-2 py-2 text-xs"
    >
      <ForwardedIconComponent
        name="AlertTriangle"
        aria-hidden="true"
        className="h-3.5 w-3.5 shrink-0 text-status-yellow"
      />
      <span>{label}</span>
    </div>
  );
}
