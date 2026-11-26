import type { useQueryFunctionType } from "@/types/api";
import { api, performStreamingRequest } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type {
  UpgradeCheckEvent,
  UpgradeCheckOutcome,
  UpgradeCheckProgress,
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

/** What the server sends when it refuses to start: a code, or the text of a pause. */
type RefusalBody = { detail: { code: string } | string };

/**
 * One streaming POST owns one run. Aborting the controller stops it on the server.
 * Progress events go to `onEvent`. How the run ended is the outcome.
 */
export async function runUpgradeCheck({
  targetVersion,
  controller,
  onEvent,
}: {
  targetVersion: string;
  controller: AbortController;
  onEvent: (event: UpgradeCheckProgress) => void;
}): Promise<UpgradeCheckOutcome> {
  let outcome: UpgradeCheckOutcome | undefined;
  let refusal: { status: number; code?: string; message?: string } | undefined;
  await performStreamingRequest({
    method: "POST",
    url: checksURL(),
    body: { target_version: targetVersion.trim() },
    buildController: controller,
    onError: (status) => {
      refusal = { status };
    },
    onData: async (data) => {
      // A refusal answers with one JSON error body instead of a stream.
      if (refusal) {
        const { detail } = data as RefusalBody;
        if (typeof detail === "string") refusal.message = detail;
        else refusal.code = detail.code;
        return false;
      }
      const event = data as UpgradeCheckEvent;
      if (event.event === "imported") {
        outcome = {
          kind: "imported",
          reportId: event.report_id,
          incomplete: event.incomplete ?? null,
          flows: event.flows ?? null,
        };
      } else if (event.event === "error") {
        outcome = {
          kind: "failed",
          code: event.code,
          message: event.message ?? "",
        };
      } else if (event.event !== "heartbeat") {
        onEvent(event);
      }
      return true;
    },
    onNetworkError: () => {},
  });
  if (outcome) return outcome;
  // A refusal also ends in an abort, so a cancel is an abort that no refusal explains.
  if (refusal) {
    return {
      kind: "failed",
      code: refusal.code,
      message: refusal.message ?? "",
    };
  }
  if (controller.signal.aborted) return { kind: "cancelled" };
  return { kind: "failed", code: "connection_lost", message: "" };
}
