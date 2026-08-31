import { debounce } from "lodash";
import { useEffect, useMemo, useState } from "react";

/**
 * Debounces the sidebar search string (300ms) used for filtering. Extracted
 * verbatim from FlowSidebarComponent (LE-1736 W33).
 */
export function useDebouncedSearch(search: string): string {
  const [debouncedSearch, setDebouncedSearch] = useState(search);

  const debouncedSetSearch = useMemo(
    () => debounce((value: string) => setDebouncedSearch(value), 300),
    [],
  );

  useEffect(() => {
    debouncedSetSearch(search);
    return () => debouncedSetSearch.cancel();
  }, [search, debouncedSetSearch]);

  return debouncedSearch;
}
