import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";
import type { ReloadBundleResponse, ReloadInProgressDetail } from "./types";

interface ReloadBundleVariables {
  extensionId: string;
  bundleName: string;
}

/**
 * POST `/api/v1/extensions/{extensionId}/bundles/{bundleName}/reload`.
 *
 * Two distinct failure shapes the caller must handle:
 *
 *  - 409 Conflict with detail.code === "reload-in-progress" -- another
 *    reload for the same Bundle is already running.  Surfaces as a thrown
 *    Error with a stable code on the message so the caller can render the
 *    fix hint without parsing free text.
 *  - 200 OK with body.ok === false -- the reload pipeline ran but the new
 *    Bundle source had structural problems (broken module, missing path,
 *    name mismatch).  The body still carries typed errors with hints; the
 *    caller surfaces them inline.  This matches the validate-style endpoint
 *    convention used elsewhere in the API.
 *
 * Anything else (auth, transport, 5xx) bubbles up via extractApiErrorMessage.
 *
 * TODO: once the extension events pipeline lands, this hook should still
 * fire the POST for ergonomics (the user clicked Reload and expects an
 * immediate response), but the success / failure toast wiring will move to
 * a `useExtensionEvents("bundle_reloaded" | "bundle_reload_failed")`
 * listener so multi-tab / multi-worker scenarios surface the swap exactly
 * once.
 */
export const useReloadBundle: useMutationFunctionType<
  undefined,
  ReloadBundleVariables,
  ReloadBundleResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function reloadBundle(
    payload: ReloadBundleVariables,
  ): Promise<ReloadBundleResponse> {
    const url = `${getURL("EXTENSIONS")}/${payload.extensionId}/bundles/${payload.bundleName}/reload`;
    try {
      const res = await api.post<ReloadBundleResponse>(url);
      return res.data;
    } catch (error: unknown) {
      // Surface 409 reload-in-progress with a stable, parseable shape so
      // the caller can branch on the code without inspecting status codes.
      const detail = (error as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      if (
        detail &&
        typeof detail === "object" &&
        (detail as ReloadInProgressDetail).code === "reload-in-progress"
      ) {
        const inProgress = detail as ReloadInProgressDetail;
        throw new Error(`reload-in-progress: ${inProgress.message}`);
      }
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to reload bundle",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    ReloadBundleResponse,
    Error,
    ReloadBundleVariables
  > = mutate(["useReloadBundle"], reloadBundle, options);

  return mutation;
};
