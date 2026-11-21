import { useId } from "react";
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

/**
 * A picker that can't offer models and has nothing to press. It stays in the
 * tab order, named by its message and its field, so keyboard and screen-reader
 * users reach it like the picker it replaces.
 */
export function ModelInputNotice({
  label,
  testId,
  ariaLabelledBy,
}: {
  label: string;
  testId: string;
  ariaLabelledBy?: string;
}): JSX.Element {
  const textId = useId();
  return (
    <div
      role="status"
      tabIndex={0}
      aria-labelledby={[textId, ariaLabelledBy].filter(Boolean).join(" ")}
      data-testid={testId}
      className="flex w-full items-center gap-2 rounded-md py-2 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
    >
      <ForwardedIconComponent
        name="AlertTriangle"
        aria-hidden="true"
        className="h-3.5 w-3.5 shrink-0 text-status-yellow"
      />
      <span id={textId}>{label}</span>
    </div>
  );
}
