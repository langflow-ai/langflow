import { useMemo } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import LangflowLogo from "@/assets/LangflowLogoColor.svg?react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AssistantConfigResponse, ModelOption } from "../assistant.types";

const PROVIDER_ICONS: Record<string, string> = {
  Anthropic: "Anthropic",
  OpenAI: "OpenAI",
  "Google Generative AI": "GoogleGenerativeAI",
  Groq: "Groq",
  Ollama: "Ollama",
};

type TerminalHeaderProps = {
  onClose: () => void;
  configData?: AssistantConfigResponse;
  selectedModel: string | null;
  onModelChange: (value: string) => void;
};

export const TerminalHeader = ({
  onClose,
  configData,
  selectedModel,
  onModelChange,
}: TerminalHeaderProps) => {
  const modelOptions = useMemo((): ModelOption[] => {
    if (!configData?.providers) return [];

    const options: ModelOption[] = [];
    for (const provider of configData.providers) {
      if (provider.configured) {
        for (const model of provider.models) {
          options.push({
            value: `${provider.name}:${model.name}`,
            label: model.display_name,
            provider: provider.name,
          });
        }
      }
    }
    return options;
  }, [configData]);

  const selectedOption = modelOptions.find((opt) => opt.value === selectedModel);
  const hasMultipleProviders =
    new Set(modelOptions.map((m) => m.provider)).size > 1;

  return (
    <div className="flex items-center justify-between border-b border-border bg-background px-4 py-2">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <LangflowLogo className="h-4 w-4" />
          <span className="font-mono text-sm font-medium text-foreground">
            AI Console
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Select
          value={selectedModel ?? ""}
          onValueChange={onModelChange}
          disabled={modelOptions.length === 0}
        >
          <SelectTrigger className="h-7 w-auto min-w-[140px] border-border bg-muted text-xs text-foreground hover:bg-accent focus:ring-0 focus:ring-offset-0 disabled:opacity-50">
            <div className="flex items-center gap-1.5">
              <ForwardedIconComponent
                name={selectedOption ? (PROVIDER_ICONS[selectedOption.provider] || "Bot") : "Bot"}
                className="h-3 w-3 text-muted-foreground"
              />
              <SelectValue placeholder="Select model">
                {selectedOption ? (
                  <span>
                    {hasMultipleProviders && (
                      <span className="text-muted-foreground">
                        {selectedOption.provider} /{" "}
                      </span>
                    )}
                    {selectedOption.label}
                  </span>
                ) : modelOptions.length === 0 ? (
                  "No models"
                ) : (
                  "Select model"
                )}
              </SelectValue>
            </div>
          </SelectTrigger>
          <SelectContent className="max-h-[300px] border-border bg-muted">
            {configData?.providers && configData.providers.length > 0 ? (
              configData.providers.map((provider) => (
                <SelectGroup key={provider.name}>
                  <SelectLabel className="flex items-center gap-1.5 px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                    <ForwardedIconComponent
                      name={PROVIDER_ICONS[provider.name] || "Bot"}
                      className="h-3 w-3"
                    />
                    {provider.name}
                  </SelectLabel>
                  {provider.models.map((model) => (
                    <SelectItem
                      key={`${provider.name}:${model.name}`}
                      value={`${provider.name}:${model.name}`}
                      className="cursor-pointer text-xs text-foreground"
                    >
                      {model.display_name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))
            ) : (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                Configure a model provider
              </div>
            )}
          </SelectContent>
        </Select>
        <Button
          variant="ghost"
          size="iconSm"
          onClick={onClose}
          className="text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};
