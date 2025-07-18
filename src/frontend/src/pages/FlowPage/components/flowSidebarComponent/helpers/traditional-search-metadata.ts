import type { APIDataType } from "@/types/api";
import { searchInMetadata } from "./search-on-metadata";

export const traditionalSearchMetadata = (
  data: APIDataType,
  searchTerm: string,
) => {
  return Object.fromEntries(
    Object.entries(data).map(([category, items]) => {
      const filteredItems = Object.fromEntries(
        Object.entries(items).filter(
          ([key, item]) =>
            item.metadata && searchInMetadata(item.metadata, searchTerm),
        ),
      );
      return [category, filteredItems];
    }),
  );
};
