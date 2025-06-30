import { VALID_CATEGORIES } from "@/constants/constants";
import useAuthStore from "@/stores/authStore";
import { useQueryFunctionType } from "@/types/api";
import { GlobalVariable } from "@/types/global_variables";
import { UseQueryResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetVariableParams {
  category: string;
  variableName: string;
}

const DEFAULT_VARIABLE_RESPONSE: GlobalVariable = {
  id: "",
  name: "",
  value: "",
  category: "",
  type: "",
  default_fields: [],
};

export const useGetCategoryVariable: useQueryFunctionType<
  GetVariableParams,
  GlobalVariable
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const { category, variableName } = params || {};

  const getCategoryVariableFn = async (): Promise<GlobalVariable> => {
    if (!isAuthenticated) return DEFAULT_VARIABLE_RESPONSE;

    if (!category || !variableName) {
      throw new Error("Category and variable name are required");
    }

    if (!VALID_CATEGORIES.includes(category)) {
      throw new Error(
        `Invalid category. Must be one of: ${VALID_CATEGORIES.join(", ")}`,
      );
    }

    try {
      const { data }: { data: GlobalVariable[] } = await api.get(
        `${getURL("VARIABLES")}/category/${category.toLowerCase()}`,
      );

      const variable = data.find((v) => v.name === variableName);

      return variable ?? DEFAULT_VARIABLE_RESPONSE;
    } catch (error) {
      console.warn(
        `Failed to get variable ${variableName} from ${category} category:`,
        error,
      );
      return DEFAULT_VARIABLE_RESPONSE;
    }
  };

  const queryResult: UseQueryResult<GlobalVariable> = query(
    ["category-variable", category, variableName],
    getCategoryVariableFn,
    {
      enabled: isAuthenticated && !!category && !!variableName,
      ...options,
    },
  );

  return queryResult;
};
