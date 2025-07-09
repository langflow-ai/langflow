import type { APIDataType } from "@/types/api";
import type { FuseResult } from "fuse.js";

export const combinedResultsFn = (
  fuseResults: FuseResult<any>[],
  data: APIDataType,
) => {
  return Object.fromEntries(
    Object.entries(data).map(([category]) => {
      const categoryResults = fuseResults.filter(
        (result) => result.item.category === category,
      );
      const filteredItems = Object.fromEntries(
        categoryResults.map((result) => [result.item.key, result.item]),
      );
      return [category, filteredItems];
    }),
  );
};
