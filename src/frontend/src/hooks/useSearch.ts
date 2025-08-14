import Fuse from "fuse.js";
import { useMemo, useState } from "react";

export const useSearch = <T>(items: T[]) => {
  const [query, setQuery] = useState("");

  const fuse = useMemo(() => {
    return new Fuse(items, {
      threshold: 0.2,
    });
  }, [items]);

  const filteredItems = useMemo(() => {
    if (!query.trim()) return items;

    const results = fuse.search(query);
    return results.map((result) => result.item);
  }, [fuse, query, items]);

  return {
    query,
    setQuery,
    filteredItems,
  };
};
