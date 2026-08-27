import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import type { ProviderScopeParams } from "@/controllers/API/helpers/provider-scope";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import CustomModelProvidersEmptyState from "@/customization/components/custom-model-providers-empty-state";
import type { ModelTypeFilter } from "@/types/models";
import ProviderListItem from "./ProviderListItem";
import { Provider } from "./types";

export interface ProviderListProps extends ProviderScopeParams {
  modelType: ModelTypeFilter;
  onProviderSelect?: (provider: Provider) => void;
  selectedProviderName?: string | null;
  /** Case-insensitive substring filter applied to the provider name. */
  query?: string;
}

const ProviderList = ({
  modelType,
  onProviderSelect,
  selectedProviderName,
  query,
  flowId,
  projectId,
}: ProviderListProps) => {
  const { t } = useTranslation();
  const {
    data: rawProviders = [],
    isLoading,
    isFetching,
    fetchStatus,
    isError,
  } = useGetModelProviders({
    includeDeprecated: true,
    flowId,
    projectId,
    purpose: "configure",
  });

  const trimmedQuery = (query ?? "").trim().toLowerCase();

  const filteredProviders: Provider[] = useMemo(() => {
    const matchesQuery = (providerName: string): boolean =>
      trimmedQuery.length === 0 ||
      providerName.toLowerCase().includes(trimmedQuery);

    return rawProviders
      .filter((provider) => matchesQuery(provider.provider))
      .map((provider) => {
        const matchingModels =
          provider?.models?.filter((model) =>
            modelType === "all"
              ? true
              : model?.metadata?.model_type === modelType,
          ) || [];

        return {
          provider: provider.provider,
          icon: provider.icon,
          is_enabled: provider.is_enabled,
          is_configured: provider.is_configured,
          model_count: matchingModels.length,
          models: matchingModels,
          api_docs_url: provider.api_docs_url,
          live_discovery: provider.live_discovery,
        };
      });
  }, [rawProviders, modelType, trimmedQuery]);

  const handleProviderSelect = (provider: Provider) => {
    onProviderSelect?.(provider);
  };

  const isLoadingProviders =
    isLoading || isFetching || fetchStatus === "paused";

  if (isLoadingProviders) {
    return (
      <div
        className="text-muted-foreground px-4 py-2"
        data-testid="provider-list-loading"
      >
        <LoadingTextComponent text={t("modelProviders.loadingProviders")} />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="text-muted-foreground px-4 py-2 text-sm"
        data-testid="provider-list-error"
      >
        {t("modelProviders.errorUnexpected")}
      </div>
    );
  }

  if (trimmedQuery.length > 0 && filteredProviders.length === 0) {
    return (
      <div
        className="text-muted-foreground px-4 py-2 text-sm"
        data-testid="provider-list-empty"
      >
        {t("modelProviders.noProvidersMatch", {
          defaultValue: "No providers match your search.",
        })}
      </div>
    );
  }

  return (
    <CustomModelProvidersEmptyState
      kind="providers"
      show={filteredProviders.length === 0}
    >
      <div className="flex flex-col gap-1" data-testid="provider-list">
        {filteredProviders.map((provider) => (
          <ProviderListItem
            key={provider.provider}
            provider={provider}
            showIcon={selectedProviderName !== null}
            isSelected={selectedProviderName === provider.provider}
            onSelect={handleProviderSelect}
          />
        ))}
      </div>
    </CustomModelProvidersEmptyState>
  );
};

export default ProviderList;
