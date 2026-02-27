import type { ChunkPreview } from "./types";

export function formatFileSize(files: File[]): string {
  const bytes = files.reduce((acc, file) => acc + file.size, 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export async function generateChunkPreviewsFromFiles(
  files: File[],
  selectedFileIndex: number,
  chunkSize: number,
  chunkOverlap: number,
  separator: string,
): Promise<ChunkPreview[]> {
  if (files.length === 0) return [];

  const allPreviews: ChunkPreview[] = [];
  const actualSeparator = separator.replace(/\\n/g, "\n").replace(/\\t/g, "\t");

  const filesToProcess = [files[selectedFileIndex] || files[0]].filter(Boolean);

  for (const file of filesToProcess) {
    const text = await file.text();

    // Simple chunking simulation
    let chunks: string[] = [];
    const separatorChunks = actualSeparator
      ? text.split(actualSeparator).filter((c) => c.trim())
      : [];
    if (separatorChunks.length > 1) {
      chunks = separatorChunks;
    } else {
      const step = Math.max(1, chunkSize - chunkOverlap);
      for (let i = 0; i < text.length; i += step) {
        chunks.push(text.slice(i, i + chunkSize));
      }
    }

    // Take up to 3 chunks per file
    const previewChunks = chunks.slice(0, 3);
    let position = 0;

    for (let i = 0; i < previewChunks.length; i++) {
      const chunk = previewChunks[i];
      if (chunk.trim()) {
        allPreviews.push({
          content: chunk.trim().slice(0, chunkSize),
          index: allPreviews.length,
          metadata: {
            source: file.name,
            start: position,
            end: position + chunk.length,
          },
        });
      }
      position += chunk.length + actualSeparator.length;
    }
  }

  return allPreviews;
}
