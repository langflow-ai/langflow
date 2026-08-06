import {
  ACTIVE_DB_PROVIDER_VARIABLE,
  type DBProviderOption,
} from "@/constants/dbProviderConstants";
import { VARIABLE_CATEGORY } from "@/constants/providerConstants";
import {
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";

/**
 * Global-variable plumbing for the DB Providers page: the variables
 * query plus the create-or-update primitives the page persists through.
 */
export function useDBProviderVariables() {
  const { data: globalVariables = [] } = useGetGlobalVariables();

  const { mutateAsync: createGlobalVariable, isPending: isCreating } =
    usePostGlobalVariables();
  const { mutateAsync: updateGlobalVariable, isPending: isUpdating } =
    usePatchGlobalVariables();

  const isPending = isCreating || isUpdating;

  const findVariable = (name: string) =>
    globalVariables.find((variable) => variable.name === name);

  const setVariable = async ({
    name,
    value,
    isSecret,
  }: {
    name: string;
    value: string;
    isSecret: boolean;
  }) => {
    const existingVariable = findVariable(name);
    if (existingVariable) {
      await updateGlobalVariable({ id: existingVariable.id, value });
      return;
    }

    await createGlobalVariable({
      name,
      value,
      type: isSecret ? "Credential" : "Generic",
      category: VARIABLE_CATEGORY.GLOBAL,
      default_fields: [],
    });
  };

  const activateProvider = async (provider: DBProviderOption) => {
    const activeProviderVariable = findVariable(ACTIVE_DB_PROVIDER_VARIABLE);
    if (activeProviderVariable) {
      await updateGlobalVariable({
        id: activeProviderVariable.id,
        value: provider.id,
      });
      return;
    }

    await createGlobalVariable({
      name: ACTIVE_DB_PROVIDER_VARIABLE,
      value: provider.id,
      type: "Generic",
      category: VARIABLE_CATEGORY.SETTINGS,
      default_fields: [],
    });
  };

  return {
    globalVariables,
    isPending,
    findVariable,
    setVariable,
    activateProvider,
  };
}
