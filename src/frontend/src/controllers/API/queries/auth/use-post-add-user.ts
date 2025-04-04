import { useKeycloakAuth } from "@/hooks/useKeycloakAuth";
import { Users, useMutationFunctionType } from "@/types/api";
import { UserInputType } from "@/types/components";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useAddUser: useMutationFunctionType<undefined, UserInputType> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();
  const { isKeycloakEnabled } = useKeycloakAuth();

  const addUserFunction = async (
    user: UserInputType,
  ): Promise<Array<Users>> => {
    if (isKeycloakEnabled) {
      throw new Error(
        "User creation is disabled when Keycloak is enabled. Please manage users through Keycloak.",
      );
    }
    const res = await api.post(`${getURL("USERS")}/`, user);
    return res.data;
  };

  const mutation: UseMutationResult<Array<Users>, any, UserInputType> = mutate(
    ["useAddUser"],
    addUserFunction,
    options,
  );

  return mutation;
};
