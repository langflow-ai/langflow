import type { RevisionPage } from "@/types/flow/revision";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const PAGE_SIZE = 50;
/** The largest page the server returns. */
export const MAX_PAGE_SIZE = 200;
// Revisions start at 1, so 0 stands for "from the newest entry".
const NEWEST = 0;

export const getFlowRevisions = async (
  flowId: string,
  before: number = NEWEST,
  limit: number = PAGE_SIZE,
): Promise<RevisionPage> => {
  const response = await api.get<RevisionPage>(
    `${getURL("FLOWS")}/${flowId}/revisions`,
    {
      params: {
        limit,
        include: "operations",
        ...(before > NEWEST ? { before } : {}),
      },
    },
  );
  return response.data;
};

/** The flow's timeline, newest first, loaded a page at a time. */
export const useGetFlowRevisions = (
  flowId: string,
  options?: { enabled?: boolean; refetchInterval?: number },
) => {
  const { infiniteQuery } = UseRequestProcessor();

  return infiniteQuery<RevisionPage>({
    queryKey: ["useGetFlowRevisions", { flowId }],
    queryFn: ({ pageParam }) => getFlowRevisions(flowId, pageParam),
    initialPageParam: NEWEST,
    getNextPageParam: (lastPage) => lastPage.next_before ?? undefined,
    enabled: !!flowId && (options?.enabled ?? true),
    refetchInterval: options?.refetchInterval,
  });
};
