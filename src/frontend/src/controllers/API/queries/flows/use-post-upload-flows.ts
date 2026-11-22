import type { AxiosError } from "axios";
import { refetchQueriesFresh } from "@/controllers/API/helpers/query-cache";
import { useFolderStore } from "@/stores/foldersStore";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import {
  getCreateFlowPayload,
  type IPostAddFlow,
  type PostAddFlowErrorResponse,
} from "./use-post-add-flow";

export const usePostUploadFlows: useMutationFunctionType<
  undefined,
  IPostAddFlow[],
  FlowType[],
  AxiosError<PostAddFlowErrorResponse>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const postUploadFlows = async (
    flows: IPostAddFlow[],
  ): Promise<FlowType[]> => {
    const formData = new FormData();
    formData.append(
      "file",
      new Blob([JSON.stringify({ flows: flows.map(getCreateFlowPayload) })], {
        type: "application/json",
      }),
      "flows.json",
    );
    const response = await api.post<FlowType[]>(
      `${getURL("FLOWS")}/upload/`,
      formData,
    );
    return response.data;
  };

  return mutate(["usePostUploadFlows"], postUploadFlows, {
    ...options,
    onSettled: (response) => {
      if (!response) return;
      void refetchQueriesFresh(queryClient, {
        queryKey: [
          "useGetRefreshFlowsQuery",
          { get_all: true, header_flows: true },
        ],
      });
      for (const folderId of new Set(
        response.map((flow) => flow.folder_id ?? myCollectionId),
      )) {
        void refetchQueriesFresh(queryClient, {
          queryKey: ["useGetFolder", folderId],
        });
      }
    },
  });
};
