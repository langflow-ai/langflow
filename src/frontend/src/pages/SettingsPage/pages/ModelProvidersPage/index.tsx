import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ModelProvidersContent from "@/modals/modelProviderModal/components/ModelProvidersContent";

export default function ModelProvidersPage() {
  const { t } = useTranslation();
  return (
    <div className="flex w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            {t("modelProviders.pageTitle")}
            <ForwardedIconComponent
              name="BrainCircuit"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("modelProviders.pageDescription")}
          </p>
        </div>
      </div>
      <div className="flex w-full h-[calc(100vh-305px)] border rounded-lg overflow-hidden">
        <ModelProvidersContent modelType="all" />
      </div>
    </div>
  );
}
