import { useTranslation } from "react-i18next";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { SearchConfigTrigger } from "./searchConfigTrigger";

interface NoResultsMessageProps {
  onClearSearch: () => void;
  message?: string;
  clearSearchText?: string;
  additionalText?: string;
  showConfig?: boolean;
  setShowConfig?: (show: boolean) => void;
}

const NoResultsMessage = ({
  onClearSearch,
  message,
  clearSearchText,
  additionalText,
  showConfig = false,
  setShowConfig,
}: NoResultsMessageProps) => {
  const { t } = useTranslation();
  const resolvedMessage = message ?? t("sidebar.noComponentsFound");
  const resolvedClearSearchText = clearSearchText ?? t("sidebar.clearSearch");
  const resolvedAdditionalText =
    additionalText ?? t("sidebar.tryDifferentQuery");
  return (
    <div className="flex h-full flex-col relative">
      {ENABLE_NEW_SIDEBAR && setShowConfig && (
        <div className="absolute top-1 right-3">
          <SearchConfigTrigger
            showConfig={showConfig}
            setShowConfig={setShowConfig}
          />
        </div>
      )}
      <div className="flex h-full flex-col items-center justify-center p-3 text-center">
        <p className="text-sm text-secondary-foreground">
          {resolvedMessage}{" "}
          <a
            className="cursor-pointer underline underline-offset-4"
            onClick={onClearSearch}
          >
            {resolvedClearSearchText}
          </a>{" "}
          {resolvedAdditionalText}
        </p>
      </div>
    </div>
  );
};

export default NoResultsMessage;
