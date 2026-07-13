import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGenerateDescription } from "@/controllers/API/queries/assistant";
import useAlertStore from "@/stores/alertStore";

export default function GenerateDescriptionButton({
  flowId,
  componentId,
  currentDescription,
  onGenerated,
  disabled = false,
}: {
  flowId?: string;
  componentId?: string;
  currentDescription?: string;
  onGenerated: (description: string) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutate: generateDescription, isPending } = useGenerateDescription();

  const handleGenerate = () => {
    if (!flowId) return;
    generateDescription(
      { flowId, componentId, currentDescription },
      {
        onSuccess: onGenerated,
        onError: (error) =>
          setErrorData({
            title: t("descriptionGenerator.error"),
            list: [error instanceof Error ? error.message : t("errors.generic")],
          }),
      },
    );
  };

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-7 gap-1.5 px-2 text-xs"
      onClick={handleGenerate}
      loading={isPending}
      disabled={disabled || !flowId || isPending}
      aria-label={t("descriptionGenerator.generate")}
      data-testid={`generate-${componentId ? "node" : "flow"}-description`}
    >
      {!isPending && <ForwardedIconComponent name="Sparkles" className="h-4 w-4" />}
      {t("descriptionGenerator.generate")}
    </Button>
  );
}
