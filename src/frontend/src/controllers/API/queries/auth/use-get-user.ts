import useAuthStore from "@/stores/authStore";
import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType, Users } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
export const useGetUserData: useMutationFunctionType<undefined, any> = (
  options?,
) => {
  const setUserData = useAuthStore((state) => state.setUserData);
  const { mutate } = UseRequestProcessor();

  const getUserData = async () => {
    const response = await api.get<Users>(`${getURL("USERS")}/whoami`);
    setUserData(response["data"]);
    return response["data"];
  };

  const mutation: UseMutationResult = mutate(
    ["useGetUserData"],
    getUserData,
    options,
  );

  return mutation;
};
