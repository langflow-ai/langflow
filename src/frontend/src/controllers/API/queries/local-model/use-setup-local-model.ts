import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface SetupLocalModelResponse {
  accepted: boolean;
}

export const useSetupLocalModel: useMutationFunctionType<
  undefined,
  { consent: boolean },
  SetupLocalModelResponse,
  Error
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const setupFn = async (body: {
    consent: boolean;
  }): Promise<SetupLocalModelResponse> => {
    const response = await api.post<SetupLocalModelResponse>(
      `${getURL("LOCAL_MODEL")}/setup`,
      body,
    );
    return response.data;
  };

  return mutate(["useSetupLocalModel"], setupFn, options);
};
