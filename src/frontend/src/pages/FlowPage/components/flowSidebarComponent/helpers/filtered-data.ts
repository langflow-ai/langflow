import { APIDataType } from "@/types/api";
import { FuseResult } from "fuse.js";

export const filteredDataFn = (
  data: APIDataType,
  combinedResults,
  traditionalResults,
) => {
  return Object.fromEntries(
    Object.entries(data).map(([category, _]) => {
      const fuseItems = combinedResults[category] || {};
      const traditionalItems = traditionalResults[category] || {};

      const mergedItems = {
        ...fuseItems,
        ...traditionalItems,
      };

      return [category, mergedItems];
    }),
  );
};
