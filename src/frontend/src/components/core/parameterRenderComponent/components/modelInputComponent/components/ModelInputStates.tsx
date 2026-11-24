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

/** Error affordance shown when the initial provider/model load fails. */
export function ModelInputErrorButton({
  onRetry,
}: {
  onRetry: () => void;
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
      data-testid="model-input-load-failed"
      onClick={onRetry}
    >
      <span className="flex items-center gap-2 truncate text-left">
        <ForwardedIconComponent
          name="AlertTriangle"
          className="h-3.5 w-3.5 shrink-0 text-status-yellow"
        />
        <span className="truncate">{t("modelInput.loadFailed")}</span>
      </span>
      <ForwardedIconComponent name="RotateCw" className="h-3.5 w-3.5" />
    </Button>
  );
}
