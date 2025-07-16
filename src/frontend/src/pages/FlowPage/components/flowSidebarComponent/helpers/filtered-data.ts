import type { APIDataType } from "@/types/api";

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
