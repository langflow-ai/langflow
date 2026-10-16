import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useUtilityStore } from "@/stores/utilityStore";
import {
  bulkTriggers,
  deleteTrigger,
  disableTrigger,
  enableTrigger,
  getTrigger,
  getTriggerIngress,
  listTriggerEvents,
  listTriggers,
  replayTriggerEvent,
  rotateTriggerSigningSecret,
  testTrigger,
} from "./api";
import { triggersKeys } from "./keys";
import type {
  TriggerBulkAction,
  TriggerBulkRequest,
  TriggerBulkResult,
  TriggerEventRead,
  TriggerIngressRead,
  TriggerListParams,
  TriggerRead,
  TriggerSigningSecretRead,
} from "./types";

/** Events are fetched one window at a time; the API has no total count. */
export const TRIGGER_EVENTS_PAGE_SIZE = 50;

/**
 * Triggers converge by polling, not a stream: the badge must match the API
 * within one `trigger_polling_interval`. Polling pauses while the tab is
 * hidden and resumes on focus.
 */
export const useTriggerPollingInterval = (): number =>
  useUtilityStore((state) => state.triggerPollingInterval);

export const useInvalidateTriggers = () => {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: triggersKeys.all });
};

export const useTriggersQuery = (
  params: TriggerListParams = {},
  options?: { enabled?: boolean; poll?: boolean },
) => {
  const interval = useTriggerPollingInterval();
  const poll = options?.poll ?? true;
  return useQuery<TriggerRead[]>({
    queryKey: triggersKeys.list(params),
    queryFn: () => listTriggers(params),
    enabled: options?.enabled ?? true,
    refetchInterval: poll && interval > 0 ? interval : false,
    refetchIntervalInBackground: false,
    retry: 1,
  });
};

export const useTriggerEventsQuery = (
  triggerId: string | undefined,
  options?: { limit?: number; enabled?: boolean },
) => {
  const interval = useTriggerPollingInterval();
  const limit = options?.limit ?? TRIGGER_EVENTS_PAGE_SIZE;
  return useQuery<TriggerEventRead[]>({
    queryKey: [...triggersKeys.events(triggerId ?? "none"), limit],
    queryFn: () => listTriggerEvents(triggerId as string, { limit }),
    enabled: Boolean(triggerId) && (options?.enabled ?? true),
    refetchInterval: interval > 0 ? interval : false,
    refetchIntervalInBackground: false,
    retry: 1,
  });
};

export const useTriggerIngressQuery = (
  triggerId: string | undefined,
  enabled = true,
) =>
  useQuery<TriggerIngressRead>({
    queryKey: triggersKeys.ingress(triggerId ?? "none"),
    queryFn: () => getTriggerIngress(triggerId as string),
    enabled: Boolean(triggerId) && enabled,
    retry: 1,
  });

const useTriggerMutation = <TData, TVariables>(
  mutationFn: (variables: TVariables) => Promise<TData>,
) => {
  const invalidate = useInvalidateTriggers();
  return useMutation<TData, unknown, TVariables>({
    mutationFn,
    onSettled: invalidate,
  });
};

export const useEnableTriggerMutation = () =>
  useTriggerMutation<TriggerRead, string>(enableTrigger);

export const useDisableTriggerMutation = () =>
  useTriggerMutation<TriggerRead, string>(disableTrigger);

export const useDeleteTriggerMutation = () =>
  useTriggerMutation<void, string>(deleteTrigger);

export const useTestTriggerMutation = () =>
  useTriggerMutation<TriggerEventRead, string>(testTrigger);

export const useReplayTriggerEventMutation = () =>
  useTriggerMutation<TriggerEventRead, { triggerId: string; eventId: string }>(
    ({ triggerId, eventId }) => replayTriggerEvent(triggerId, eventId),
  );

/**
 * The secret lives only in the mutation's result: it is never written to the
 * query cache, so it disappears with the dialog that shows it.
 */
export const useRotateSigningSecretMutation = () =>
  useTriggerMutation<TriggerSigningSecretRead, string>(
    rotateTriggerSigningSecret,
  );

export const useBulkTriggersMutation = () =>
  useTriggerMutation<
    TriggerBulkResult,
    { action: TriggerBulkAction; body: TriggerBulkRequest }
  >(({ action, body }) => bulkTriggers(action, body));

/** Dry runs change nothing, so they skip invalidation. */
export const useBulkTriggersDryRunMutation = () =>
  useMutation<
    TriggerBulkResult,
    unknown,
    { action: TriggerBulkAction; body: Omit<TriggerBulkRequest, "dry_run"> }
  >({
    mutationFn: ({ action, body }) =>
      bulkTriggers(action, { ...body, dry_run: true }),
  });

/** One trigger, polled, so an open drawer or dialog never shows a stale state. */
export const useTriggerQuery = (triggerId: string | undefined) => {
  const interval = useTriggerPollingInterval();
  return useQuery<TriggerRead>({
    queryKey: triggersKeys.one(triggerId ?? "none"),
    queryFn: () => getTrigger(triggerId as string),
    enabled: Boolean(triggerId),
    refetchInterval: interval > 0 ? interval : false,
    refetchIntervalInBackground: false,
    retry: 1,
  });
};
