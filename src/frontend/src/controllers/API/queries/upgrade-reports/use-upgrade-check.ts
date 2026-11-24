import type { useQueryFunctionType } from "@/types/api";
import { api, performStreamingRequest } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type {
  UpgradeCheckEvent,
  UpgradeCheckRefusal,
  UpgradeReleases,
} from "./types";

const checksURL = (path?: string) =>
  getURL("UPGRADE_REPORTS", { path: path ? `checks/${path}` : "checks" });

export const useGetUpgradeReleases: useQueryFunctionType<
  undefined,
  UpgradeReleases
> = (options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useGetUpgradeReleases"],
    async () => (await api.get(checksURL("releases"))).data,
    { retry: false, staleTime: 5 * 60 * 1000, ...options },
  );
};

/** One streaming POST owns one run. Aborting the controller stops it on the server. */
export async function runUpgradeCheck({
  targetVersion,
  controller,
  onEvent,
}: {
  targetVersion: string;
  controller: AbortController;
  onEvent: (event: UpgradeCheckEvent) => void;
}): Promise<UpgradeCheckRefusal | undefined> {
  let refused: UpgradeCheckRefusal | undefined;
  await performStreamingRequest({
    method: "POST",
    url: checksURL(),
    body: { target_version: targetVersion.trim() },
    buildController: controller,
    onError: (status) => {
      refused = { status };
    },
    onData: async (data) => {
      // A refusal answers with one JSON error body instead of a stream.
      if (refused) {
        const body = data as {
          code?: string;
          message?: string;
          detail?: { code?: string; message?: string } | string;
        };
        const detail =
          typeof body.detail === "object" && body.detail ? body.detail : body;
        refused.code = detail.code;
        refused.message =
          detail.message ??
          (typeof body.detail === "string" ? body.detail : undefined);
        return false;
      }
      onEvent(data as UpgradeCheckEvent);
      return true;
    },
    onNetworkError: () => {
      if (!controller.signal.aborted) refused ??= { status: 0 };
    },
  });
  return refused;
}
