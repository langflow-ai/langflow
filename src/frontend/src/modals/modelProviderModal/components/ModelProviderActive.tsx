import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";

export interface ModelProviderActiveProps {
  /** List of active LLM model names */
  activeLLMs: string[];
  /** List of active embedding model names */
  activeEmbeddings: string[];
}

/**
 * Displays badges for currently active LLM and embedding models.
 * Shown in the provider edit panel to indicate which models are enabled.
 */
const ModelProviderActive = ({
  activeLLMs,
  activeEmbeddings,
}: ModelProviderActiveProps) => {
  return (
    <div
      className="flex flex-col p-4 border-t overflow-y-auto h-[178.5px]"
      data-testid="model-provider-active"
    >
      <div className="text-[13px] font-medium flex items-center gap-1">
        Models{" "}
        <ForwardedIconComponent
          name="info"
          className="w-4 h-4 text-muted-foreground ml-1"
        />{" "}
      </div>
      {activeLLMs.length > 0 && (
        <div className="pt-4">
          <div className="text-[10px] text-muted-foreground">LLM</div>
          <div className="flex flex-row gap-2 mt-2 flex-wrap">
            {activeLLMs.map((model) => (
              <Badge
                key={model}
                variant="secondaryStatic"
                size="sq"
                className="whitespace-nowrap"
                data-testid={`active-llm-badge-${model}`}
              >
                {model}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {activeEmbeddings.length > 0 && (
        <>
          <div className="text-[10px] pt-4 text-muted-foreground">
            Embeddings
          </div>
          <div className="flex flex-row gap-2 mt-2 flex-wrap">
            {activeEmbeddings.map((model) => (
              <Badge
                key={model}
                variant="secondaryStatic"
                size="sq"
                className="whitespace-nowrap"
                data-testid={`active-embedding-badge-${model}`}
              >
                {model}
              </Badge>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default ModelProviderActive;
