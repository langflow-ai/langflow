import type { APIDataType } from "@/types/api";

export const applyComponentFilter = (
  filteredData: APIDataType,
  getFilterComponent,
) => {
  const [category, component] = getFilterComponent.split(".");
  return Object.fromEntries(
    Object.entries(filteredData).map(([cat, items]) => [
      cat,
      Object.fromEntries(
        Object.entries(items).filter(
          ([name, _]) => name === component && cat === category,
        ),
      ),
    ]),
  );
};
