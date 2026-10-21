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

/**
 * A picker that cannot offer models: the load failed (with `onRetry`), or the
 * field asks for a model kind this picker does not know (without). It stays
 * focusable either way, so keyboard and screen-reader users reach the message.
 */
export function ModelInputErrorButton({
  label,
  onRetry,
  testId,
}: {
  label: string;
  onRetry?: () => void;
  testId: string;
}): JSX.Element {
  return (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
      data-testid={testId}
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
      {onRetry && (
        <ForwardedIconComponent name="RotateCw" className="h-3.5 w-3.5" />
      )}
    </Button>
  );
}
