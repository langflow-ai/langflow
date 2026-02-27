import type { ChunkPreview } from "../types";

export function ChunkPreviewCard({
  chunk,
  index,
}: {
  chunk: ChunkPreview;
  index: number;
}) {
  return (
    <div className="flex flex-col rounded-lg border bg-muted/30 p-3 h-full">
      <div className="mb-2 flex items-center justify-between shrink-0">
        <span className="text-xs font-medium text-muted-foreground">
          Chunk {index + 1}
        </span>
      </div>
      <div className="overflow-y-auto rounded bg-background p-2 text-xs font-mono flex-1 min-h-0 whitespace-pre-wrap break-words">
        {chunk.content}
      </div>
    </div>
  );
}
