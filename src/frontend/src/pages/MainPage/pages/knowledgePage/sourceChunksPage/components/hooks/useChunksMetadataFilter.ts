import { useMemo } from "react";
import { useGetKbMetadataKeys } from "@/controllers/API/queries/knowledge-bases/use-get-kb-metadata-keys";

interface UseChunksMetadataFilterOptions {
  kbName: string;
  /** Outer popover open state — gates the network query. */
  enabled: boolean;
  /** Currently typed/selected key. Drives the value suggestion list. */
  selectedKey: string;
}

interface UseChunksMetadataFilterResult {
  availableKeys: string[];
  valueSuggestions: string[];
  isLoading: boolean;
  hasKeys: boolean;
  truncated: boolean;
  refetch: () => void;
}

/**
 * Data hook for the chunks-browser metadata filter.
 *
 * Wraps `useGetKbMetadataKeys` and derives the two lists the UI actually
 * consumes (sorted available keys, value suggestions for the typed key)
 * so the filter component itself stays free of memoization plumbing.
 */
export const useChunksMetadataFilter = ({
  kbName,
  enabled,
  selectedKey,
}: UseChunksMetadataFilterOptions): UseChunksMetadataFilterResult => {
  const {
    data: metadataKeys,
    isLoading,
    refetch,
  } = useGetKbMetadataKeys(
    { kb_name: kbName },
    { enabled: enabled && !!kbName },
  );

  const availableKeys = useMemo(
    () => Object.keys(metadataKeys?.keys ?? {}).sort(),
    [metadataKeys],
  );

  const valueSuggestions = useMemo(() => {
    const trimmed = selectedKey.trim();
    if (!trimmed) return [] as string[];
    return metadataKeys?.keys?.[trimmed] ?? [];
  }, [selectedKey, metadataKeys]);

  return {
    availableKeys,
    valueSuggestions,
    isLoading,
    hasKeys: availableKeys.length > 0,
    truncated: !!metadataKeys?.truncated,
    refetch: () => {
      void refetch();
    },
  };
};
