import { Badge } from '@/components/ui/badge';

interface ModelProviderActiveProps {
  activeLLMs: string[];
  activeEmbeddings: string[];
}

const ModelProviderActive = ({
  activeLLMs,
  activeEmbeddings,
}: ModelProviderActiveProps) => {
  return (
    <div className="flex flex-col p-4 border-t overflow-y-auto h-[178.5px]">
      <div className="text-[13px] font-medium">Models</div>
      {activeLLMs.length > 0 && (
        <div className="pt-4">
          <div className="text-[10px] text-muted-foreground">LLM</div>
          <div className="flex flex-row gap-2 mt-2 flex-wrap">
            {activeLLMs.map(model => (
              <Badge
                key={model}
                variant="secondaryStatic"
                size="sq"
                className="whitespace-nowrap"
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
            {activeEmbeddings.map(model => (
              <Badge
                key={model}
                variant="secondaryStatic"
                size="sq"
                className="whitespace-nowrap"
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
