import useAuthStore from "@/stores/authStore";
import { UseMutationResult } from "@tanstack/react-query";
import { useMutationFunctionType, Users } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
export const useGetUserData: useMutationFunctionType<undefined, any> = (
  options?,
) => {
  const setUserData = useAuthStore((state) => state.setUserData);
  const { mutate } = UseRequestProcessor();

  const getUserData = async () => {
    console.debug("[useGetUserData] Calling /whoami");
    const response = await api.get<Users>(`${getURL("USERS")}/whoami`);
    console.debug("[useGetUserData] Response:", response);
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
