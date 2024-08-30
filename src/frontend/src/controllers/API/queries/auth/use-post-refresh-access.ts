import { LANGFLOW_REFRESH_TOKEN } from "@/constants/constants";
import { useMutationFunctionType } from "@/types/api";
import { Cookies } from "react-cookie";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
interface IRefreshAccessToken {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const useRefreshAccessToken: useMutationFunctionType<
  undefined,
  undefined | void,
  IRefreshAccessToken
> = (options?) => {
  const { mutate } = UseRequestProcessor();
  const cookies = new Cookies();

  async function refreshAccess(): Promise<IRefreshAccessToken> {
    const res = await api.post<IRefreshAccessToken>(`${getURL("REFRESH")}`);
    cookies.set(LANGFLOW_REFRESH_TOKEN, res.data.refresh_token, { path: "/" });

    return res.data;
  }

  const mutation = mutate(["useRefreshAccessToken"], refreshAccess, options);

  return mutation;
};
