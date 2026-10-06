import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import { api, performStreamingRequest } from "../../api";
import { getURL } from "../../helpers/constants";
import type {
  MigrationCheckEvent,
  MigrationError,
  MigrationState,
} from "./types";

export const migrationKeys = {
  all: ["migration"] as const,
};

export const useMigrationQuery = (enabled = true) =>
  useQuery<MigrationState>({
    queryKey: migrationKeys.all,
    queryFn: async () => (await api.get(getURL("MIGRATION"))).data,
    enabled,
    // An HTTP error such as record_unreadable answers the same on every try, so only a dropped connection is retried.
    retry: (count, error) => !(error as AxiosError).response && count < 3,
    // While another admin runs the check, the page follows it until it finishes.
    refetchInterval: (query) =>
      query.state.data?.record.steps.check_source?.status === "running"
        ? 5000
        : false,
  });

/**
 * Runs the source checks against `targetVersion` and hands over each line of the stream as it arrives.
 * Resolves with the refusal when the server won't start them, or status 0 if the connection fails.
 * Aborting the controller stops the checks on the server too.
 */
export async function runSourceChecks({
  targetVersion,
  controller,
  onEvent,
}: {
  targetVersion: string;
  controller: AbortController;
  onEvent: (event: MigrationCheckEvent) => void;
}): Promise<{ status: number; detail?: MigrationError } | undefined> {
  let refused: { status: number; detail?: MigrationError } | undefined;
  await performStreamingRequest({
    method: "POST",
    url: getURL("MIGRATION", { path: "checks" }),
    body: { target_version: targetVersion.trim() },
    buildController: controller,
    onError: (status) => {
      refused = { status };
    },
    onData: async (data) => {
      // A refused request answers with one JSON error body instead of a stream.
      if (refused) {
        refused.detail = (data as { detail?: MigrationError }).detail;
        return false;
      }
      onEvent(data as MigrationCheckEvent);
      return true;
    },
    // A request that never reached the server leaves the previous record intact.
    // Return that failure so the page doesn't present the previous run as its outcome.
    onNetworkError: () => {
      if (!controller.signal.aborted) refused ??= { status: 0 };
    },
  });
  return refused;
}

export const useAcceptFindingMutation = () => {
  const client = useQueryClient();
  return useMutation<MigrationState, unknown, string>({
    mutationFn: async (name) =>
      (
        await api.post(getURL("MIGRATION", { path: "accepted-findings" }), {
          name,
        })
      ).data,
    onSuccess: (state) => client.setQueryData(migrationKeys.all, state),
  });
};

export const useWithdrawFindingMutation = () => {
  const client = useQueryClient();
  return useMutation<MigrationState, unknown, string>({
    mutationFn: async (name) =>
      (
        await api.delete(getURL("MIGRATION", { path: "accepted-findings" }), {
          params: { name },
        })
      ).data,
    onSuccess: (state) => client.setQueryData(migrationKeys.all, state),
  });
};
