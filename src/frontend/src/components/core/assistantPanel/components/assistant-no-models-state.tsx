import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

export function AssistantNoModelsState() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleConfigureModels = () => {
    navigate("/settings/model-providers");
  };

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-8 pb-6">
      <div className="mb-6 flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl">
        <img
          src={langflowAssistantIcon}
          alt="Langflow Assistant"
          className="h-full w-full object-cover"
        />
      </div>
      <h3 className="mb-3 text-center text-base font-semibold leading-6 tracking-normal text-foreground">
        {t("assistant.noModelsConfigured")}
      </h3>
      <p className="mb-6 max-w-[280px] text-center text-sm text-muted-foreground">
        {t("assistant.noModelsDescription")}
      </p>
      <Button
        variant="outline"
        size="sm"
        className="gap-2 text-muted-foreground"
        onClick={handleConfigureModels}
      >
        <ForwardedIconComponent name="Settings" className="h-4 w-4" />
        {t("assistant.configureModels")}
      </Button>
    </div>
  );
}
