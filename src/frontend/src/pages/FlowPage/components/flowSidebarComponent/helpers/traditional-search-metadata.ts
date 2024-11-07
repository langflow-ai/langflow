import { APIDataType } from "@/types/api";
import { normalizeString } from "./normalize-string";
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
            normalizeString(key).includes(searchTerm) ||
            normalizeString(item.display_name).includes(searchTerm) ||
            normalizeString(category).includes(searchTerm) ||
            (item.metadata && searchInMetadata(item.metadata, searchTerm)),
        ),
      );
      return [category, filteredItems];
    }),
  );
};
