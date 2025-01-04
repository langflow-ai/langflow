import { APIDataType } from "@/types/api";

export const applyBetaFilter = (filteredData: APIDataType) => {
  return Object.fromEntries(
    Object.entries(filteredData).map(([category, items]) => [
      category,
      Object.fromEntries(
        Object.entries(items).filter(([_, value]) => !value.beta),
      ),
    ]),
  );
};
