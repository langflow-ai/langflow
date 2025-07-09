import type { Users, useMutationFunctionType } from "@/types/api";
import type { UserInputType } from "@/types/components";
import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useAddUser: useMutationFunctionType<undefined, UserInputType> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  const addUserFunction = async (
    user: UserInputType,
  ): Promise<Array<Users>> => {
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
