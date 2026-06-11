import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";

import { Model } from "@/modals/modelProviderModal/components/types";
import { cn } from "@/utils/utils";

export interface ModelProviderSelectionProps {
  availableModels: Model[];
  onModelToggle: (modelName: string, enabled: boolean) => void;
  modelType: "llm" | "embeddings" | "all";
  providerName?: string;
  isEnabledModel?: boolean;
}

interface ModelRowProps {
  model: Model;
  enabled: boolean;
  onToggle: (modelName: string, enabled: boolean) => void;
  testIdPrefix: string;
  isEnabledModel?: boolean;
  /** When true (modelType === "all" view), show the "embedding" tag on
   *  embedding models. In dedicated embedding sections the tag is redundant. */
  showEmbeddingTag?: boolean;
}

/** Tag descriptor consumed by ModelRow. */
interface CapabilityTag {
  /** Stable identifier (used in test ids and as React key). */
  id: string;
  /** Short label shown inside the Badge. */
  label: string;
}

/** Stable left-to-right ordering for the capability badges. */
const TAG_ORDER: Array<CapabilityTag["id"]> = [
  "embedding",
  "tool",
  "reasoning",
  "vision",
  "search",
  "preview",
];

const buildCapabilityTags = (
  model: Model,
  showEmbeddingTag: boolean,
  t: (key: string, options?: { defaultValue: string }) => string,
): CapabilityTag[] => {
  const metadata = (model.metadata ?? {}) as Record<string, unknown>;
  const isEmbedding = metadata.model_type === "embeddings";
  const tags: Record<string, CapabilityTag> = {};

  if (showEmbeddingTag && isEmbedding) {
    tags.embedding = {
      id: "embedding",
      label: t("modelProviders.tag.embedding", { defaultValue: "embedding" }),
    };
  }
  if (metadata.tool_calling === true) {
    tags.tool = {
      id: "tool",
      label: t("modelProviders.tag.tool", { defaultValue: "tool" }),
    };
  }
  if (metadata.reasoning === true) {
    tags.reasoning = {
      id: "reasoning",
      label: t("modelProviders.tag.reasoning", { defaultValue: "reasoning" }),
    };
  }
  if (metadata.vision === true) {
    tags.vision = {
      id: "vision",
      label: t("modelProviders.tag.vision", { defaultValue: "vision" }),
    };
  }
  if (metadata.search === true) {
    tags.search = {
      id: "search",
      label: t("modelProviders.tag.search", { defaultValue: "search" }),
    };
  }
  if (metadata.preview === true) {
    tags.preview = {
      id: "preview",
      label: t("modelProviders.tag.preview", { defaultValue: "preview" }),
    };
  }

  return TAG_ORDER.map((id) => tags[id]).filter((tag): tag is CapabilityTag =>
    Boolean(tag),
  );
};

/** Single row displaying a model with its toggle switch */
const ModelRow = ({
  onToggle,
  model,
  enabled,
  testIdPrefix,
  isEnabledModel,
  showEmbeddingTag,
}: ModelRowProps) => {
  const { t } = useTranslation();
  const tags = buildCapabilityTags(model, !!showEmbeddingTag, t);

  return (
    <div className="flex flex-row items-center justify-between h-[24px]">
      <div className="flex flex-row items-center gap-2">
        <ForwardedIconComponent
          name={model.metadata?.icon || "Bot"}
          className={cn("w-5 h-5", { grayscale: !isEnabledModel })}
        />
        <span
          className={cn("text-sm", {
            "text-muted-foreground": !isEnabledModel,
          })}
        >
          {model.model_name}
        </span>
        {tags.map((tag) => (
          <Badge
            key={tag.id}
            variant="secondaryStatic"
            size="tag"
            data-testid={`${testIdPrefix}-tag-${tag.id}-${model.model_name}`}
          >
            {tag.label}
          </Badge>
        ))}
        {model.metadata?.deprecated ? (
          <Badge
            variant="secondaryStatic"
            size="tag"
            data-testid={`${testIdPrefix}-deprecated-${model.model_name}`}
          >
            {t("modelProvider.deprecated")}
          </Badge>
        ) : null}
      </div>
      {isEnabledModel && (
        <Switch
          checked={enabled}
          onCheckedChange={(checked) => onToggle(model.model_name, checked)}
          data-testid={`${testIdPrefix}-toggle-${model.model_name}`}
          aria-label={
            enabled
              ? t("modelProvider.disableModel", { modelName: model.model_name })
              : t("modelProvider.enableModel", { modelName: model.model_name })
          }
          stopPropagation
        />
      )}
    </div>
  );
};

/**
 * Displays lists of LLM and embedding models with toggle switches.
 * Allows users to enable/disable individual models for a provider.
 */
const ModelSelection = ({
  modelType = "llm",
  availableModels,
  onModelToggle,
  providerName,
  isEnabledModel,
}: ModelProviderSelectionProps) => {
  const { t } = useTranslation();
  const { data: enabledModelsData } = useGetEnabledModels();
  const [modelQuery, setModelQuery] = useState<string>("");
  const [showDeprecated, setShowDeprecated] = useState<boolean>(false);

  // Reset both the search and the deprecated disclosure when the selected
  // provider changes so neither state leaks across providers
  // (OpenRouter → Anthropic, etc.).
  useEffect(() => {
    setModelQuery("");
    setShowDeprecated(false);
  }, [providerName]);

  const isModelEnabled = (modelName: string): boolean => {
    if (!providerName || !enabledModelsData?.enabled_models) return false;
    return enabledModelsData.enabled_models[providerName]?.[modelName] ?? false;
  };

  const trimmedModelQuery = modelQuery.trim().toLowerCase();

  const matchesModelQuery = (model: Model): boolean =>
    trimmedModelQuery.length === 0 ||
    model.model_name.toLowerCase().includes(trimmedModelQuery);

  const llmModels = useMemo(
    () =>
      availableModels.filter(
        (model) =>
          model.metadata?.model_type === "llm" && matchesModelQuery(model),
      ),
    [availableModels, trimmedModelQuery],
  );
  const embeddingModels = useMemo(
    () =>
      availableModels.filter(
        (model) =>
          model.metadata?.model_type === "embeddings" &&
          matchesModelQuery(model),
      ),
    [availableModels, trimmedModelQuery],
  );

  const partitionDeprecated = (models: Model[]): [Model[], Model[]] => {
    const active: Model[] = [];
    const deprecated: Model[] = [];
    for (const model of models) {
      if (model.metadata?.deprecated) {
        deprecated.push(model);
      } else {
        active.push(model);
      }
    }
    return [active, deprecated];
  };

  const renderModelRow = (model: Model, testIdPrefix: string) => (
    <ModelRow
      key={model.model_name}
      model={model}
      enabled={isModelEnabled(model.model_name)}
      onToggle={onModelToggle}
      testIdPrefix={testIdPrefix}
      isEnabledModel={isEnabledModel}
      showEmbeddingTag={modelType === "all"}
    />
  );

  const renderModelSection = (
    title: string,
    models: Model[],
    testIdPrefix: string,
  ) => {
    if (models.length === 0) return null;
    const [activeModels, deprecatedModels] = partitionDeprecated(models);
    return (
      <div data-testid={`${testIdPrefix}-models-section`}>
        <div className="text-[13px] font-semibold text-muted-foreground">
          {title}
        </div>
        <div className="flex flex-col gap-2 pt-4">
          {activeModels.map((model) => renderModelRow(model, testIdPrefix))}
        </div>
        {deprecatedModels.length > 0 && (
          <details
            className="pt-3"
            data-testid={`${testIdPrefix}-deprecated-disclosure`}
            open={showDeprecated}
            onToggle={(event) =>
              setShowDeprecated(
                (event.currentTarget as HTMLDetailsElement).open,
              )
            }
          >
            <summary
              className="text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer select-none"
              data-testid={`${testIdPrefix}-deprecated-summary`}
            >
              {deprecatedModels.length === 1
                ? t("modelProviders.showDeprecatedSingular", {
                    defaultValue: "Show 1 deprecated model",
                  })
                : t("modelProviders.showDeprecated", {
                    count: deprecatedModels.length,
                    defaultValue: "Show {{count}} deprecated models",
                  })}
            </summary>
            <div className="flex flex-col gap-2 pt-3">
              {deprecatedModels.map((model) =>
                renderModelRow(model, testIdPrefix),
              )}
            </div>
          </details>
        )}
      </div>
    );
  };

  const isOllama = providerName?.toLowerCase() === "ollama";
  // Use the unfiltered availableModels for the empty-state check so an
  // ollama-no-models warning still fires when the search field happens to be
  // populated.
  const llmAvailableCount = availableModels.filter(
    (m) => m.metadata?.model_type === "llm",
  ).length;
  const embeddingAvailableCount = availableModels.filter(
    (m) => m.metadata?.model_type === "embeddings",
  ).length;
  const noModelsAvailable =
    (modelType === "llm" && llmAvailableCount === 0) ||
    (modelType === "embeddings" && embeddingAvailableCount === 0) ||
    (modelType === "all" && availableModels.length === 0);

  const noModelsMatchQuery =
    !noModelsAvailable &&
    trimmedModelQuery.length > 0 &&
    llmModels.length === 0 &&
    embeddingModels.length === 0;

  return (
    <div data-testid="model-provider-selection" className="flex flex-col gap-6">
      {!noModelsAvailable && availableModels.length > 0 && (
        <Input
          icon="Search"
          value={modelQuery}
          onChange={(event) => setModelQuery(event.target.value)}
          placeholder={t("modelProviders.searchModels", {
            defaultValue: "Search models…",
          })}
          aria-label={t("modelProviders.searchModels", {
            defaultValue: "Search models…",
          })}
          data-testid="model-search-input"
        />
      )}
      {noModelsMatchQuery ? (
        <div
          className="text-muted-foreground px-1 py-2 text-sm"
          data-testid="model-search-empty"
        >
          {t("modelProviders.noModelsMatch", {
            defaultValue: "No models match your search.",
          })}
        </div>
      ) : null}
      {isOllama && noModelsAvailable ? (
        <div className="flex flex-col items-center justify-center p-8 text-center border border-dashed rounded-lg bg-muted/30">
          <ForwardedIconComponent
            name="Info"
            className="w-10 h-10 mb-4 text-muted-foreground"
          />
          <h3 className="mb-2 text-sm font-semibold text-foreground">
            {t("modelProviders.noModelsAvailable")}
          </h3>
          <p className="max-w-[300px] text-xs text-muted-foreground leading-relaxed">
            {modelType === "llm"
              ? t("modelProviders.ollamaNoModelsLlm")
              : modelType === "embeddings"
                ? t("modelProviders.ollamaNoModelsEmbeddings")
                : t("modelProviders.ollamaNoModelsAll")}
          </p>
          <a
            href="https://ollama.com/library"
            target="_blank"
            rel="noreferrer"
            className="mt-6 text-xs font-medium text-primary underline underline-offset-4 hover:opacity-80 transition-opacity"
          >
            {t("modelProviders.checkOllamaLibrary")}
          </a>
        </div>
      ) : (
        <>
          {modelType === "all" ? (
            <>
              {renderModelSection(
                t("modelProviders.languageModels"),
                llmModels,
                "llm",
              )}
              {renderModelSection(
                t("modelProviders.embeddingModels"),
                embeddingModels,
                "embeddings",
              )}
            </>
          ) : modelType === "llm" ? (
            renderModelSection(
              t("modelProviders.languageModels"),
              llmModels,
              "llm",
            )
          ) : (
            renderModelSection(
              t("modelProviders.embeddingModels"),
              embeddingModels,
              "embeddings",
            )
          )}
        </>
      )}
    </div>
  );
};

export default ModelSelection;
