import { useTypesStore } from "@/stores/typesStore";

export const useGetReplacementComponents = (replacement?: string[]) => {
  const data = useTypesStore((state) => state.data);

  return replacement && Array.isArray(replacement) && replacement.length > 0
    ? replacement.map((component) => {
        const categoryName = component?.split(".")[0];
        const componentName = component?.split(".")[1];

        return (
          categoryName &&
          componentName &&
          data[categoryName][componentName].display_name
        );
      })
    : [];
};
