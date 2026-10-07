import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AxiosError, AxiosResponse } from "axios";
import { api, performStreamingRequest } from "../../api";
import { getURL } from "../../helpers/constants";
import type {
  CopyDecision,
  CopyEvent,
  CopyStepId,
  DestinationsRequest,
  DestinationsSaved,
  MigrationCheckEvent,
  MigrationError,
  MigrationJob,
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
    // Another admin can turn changes back on, or start, stop or finish a check or a copy. While changes are paused
    // or something runs, the page follows the record, so it never shows a pause or a copy that is no longer there.
    refetchInterval: (query) => {
      const record = query.state.data?.record;
      const running = Object.values(record?.steps ?? {}).some(
        (step) => step?.status === "running",
      );
      return record?.pause || running ? 5000 : false;
    },
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

/** A step's request, which answers with the new state. The page shows that state in place of the one it held. */
const useStepMutation = <Body, State extends MigrationState = MigrationState>(
  request: (body: Body) => Promise<{ data: State }>,
) => {
  const client = useQueryClient();
  return useMutation<State, AxiosError<{ detail?: MigrationError }>, Body>({
    mutationFn: async (body) => (await request(body)).data,
    onSuccess: (state) => client.setQueryData(migrationKeys.all, state),
    // A refusal can come with a change the answer doesn't carry, such as a step that reopened.
    onError: () => client.invalidateQueries({ queryKey: migrationKeys.all }),
  });
};

/** Tests each destination and saves the ones that pass. The passwords and keys stay in the server's memory. */
export const useSaveDestinationsMutation = () =>
  useStepMutation<DestinationsRequest, DestinationsSaved>((body) =>
    api.put(getURL("MIGRATION", { path: "destinations" }), body),
  );

/** Asks whether the new instance's key is this instance's key, by its fingerprint. The key is never sent. */
export const useVerifySecretKeyMutation = () =>
  useStepMutation((fingerprint: string) =>
    api.post(getURL("MIGRATION", { path: "secret-key/verify" }), {
      fingerprint,
    }),
  );

/** Stops changes to this instance. The server refuses while anything is still writing, and says what. */
export const usePauseMutation = () =>
  useStepMutation<void>(() => api.post(getURL("MIGRATION", { path: "pause" })));

/** Lets changes through again. What was backed up or copied during the pause no longer counts. */
export const useResumeMutation = () =>
  useStepMutation<void>(() =>
    api.delete(getURL("MIGRATION", { path: "pause" })),
  );

/** Sends the request the server gave for cancelling a job. Only the job's own route knows who may. */
export const useCancelJobMutation = () =>
  useMutation<unknown, AxiosError, NonNullable<MigrationJob["cancel"]>>({
    mutationFn: ({ method, url, body }) =>
      api.request({ method, url, data: body }),
  });

/** Fetches a consistent copy of this instance's SQLite database. The server keeps no copy of its own. */
export const useDownloadDatabaseMutation = () => {
  const client = useQueryClient();
  return useMutation<AxiosResponse<Blob>, AxiosError>({
    mutationFn: () =>
      api.post(getURL("MIGRATION", { path: "backup/database" }), undefined, {
        responseType: "blob",
      }),
    // The record now says when the copy was made, or why there can't be one, such as a pause that ended.
    onSettled: () => client.invalidateQueries({ queryKey: migrationKeys.all }),
  });
};

/** Records where the admin keeps the backup, which finishes the step. */
export const useConfirmBackupMutation = () =>
  useStepMutation((location: string) =>
    api.post(getURL("MIGRATION", { path: "steps/backup/confirm" }), {
      location,
    }),
  );

/**
 * Starts a copy, or a test run of one, which copies nothing.
 * It is a process of its own on the server, so it keeps going when the page is gone.
 */
export const useStartCopyMutation = (step: CopyStepId) => {
  const client = useQueryClient();
  return useMutation<unknown, AxiosError<{ detail?: MigrationError }>, boolean>(
    {
      mutationFn: (dryRun) =>
        api.post(getURL("MIGRATION", { path: `steps/${step}/runs` }), {
          dry_run: dryRun,
        }),
      // The record now says the run is on, or what changed for the server to refuse it.
      onSettled: () =>
        client.invalidateQueries({ queryKey: migrationKeys.all }),
    },
  );
};

/** Stops a run. The page learns that it ended from the run's own events. */
export const useStopCopyMutation = (step: CopyStepId) =>
  useMutation<unknown, AxiosError, string>({
    mutationFn: (runId) =>
      api.delete(getURL("MIGRATION", { path: `steps/${step}/runs/${runId}` })),
  });

/**
 * Hands over each event of a run that comes after the one numbered `after`, as it happens, down to its end.
 * Resolves with the refusal when the server has no such run, or status 0 if the connection fails.
 * Aborting the controller stops nothing on the server.
 */
export async function followCopy({
  step,
  runId,
  after,
  controller,
  onEvent,
}: {
  step: CopyStepId;
  runId: string;
  after: number;
  controller: AbortController;
  onEvent: (event: CopyEvent) => void;
}): Promise<{ status: number } | undefined> {
  let refused: { status: number } | undefined;
  await performStreamingRequest({
    method: "GET",
    url: `${getURL("MIGRATION", { path: `steps/${step}/runs/${runId}/events` })}?after=${after}`,
    buildController: controller,
    onError: (status) => {
      refused = { status };
    },
    onData: async (data) => {
      // A refusal answers with one JSON error body in place of the events. Let it end on its own:
      // returning false would abort the caller's controller, which every later attempt shares.
      if (!refused) onEvent(data as CopyEvent);
      return true;
    },
    onNetworkError: () => {
      if (!controller.signal.aborted) refused ??= { status: 0 };
    },
  });
  return refused;
}

/**
 * Records a decision the server offered about a copy, or takes it back when `made` is false.
 * It is sent as it came: with a `subject` it accepts that one item, with none it is an option for the next run.
 * An acceptance names the run whose report the item is in, and the server refuses it once another run took its place.
 */
export const useDecideMutation = () =>
  useStepMutation(
    ({
      made,
      ...decision
    }: Pick<CopyDecision, "kind" | "subject" | "run_id"> & {
      step: CopyStepId;
      made: boolean;
    }) =>
      made
        ? api.post(getURL("MIGRATION", { path: "decisions" }), decision)
        : api.delete(getURL("MIGRATION", { path: "decisions" }), {
            data: decision,
          }),
  );
