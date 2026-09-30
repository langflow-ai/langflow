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
 * Wire contract (typed-error envelope on every error path):
 *
 *  - 200 OK -- success.  Body is the full ReloadResult with ok=true,
 *    components_added/removed, warnings.
 *  - 409 Conflict, detail.code === "reload-in-progress" -- another reload
 *    for the same Bundle is already running.  Surfaces as a thrown Error
 *    with a stable code prefix on the message so the caller can branch
 *    without inspecting status codes.
 *  - 422 Unprocessable Entity -- the reload pipeline ran but rejected the
 *    new source (broken module, missing path, name mismatch).  Body is
 *    `{...primaryError, result: ReloadResult}` per the typed-error
 *    contract.  The hook unwraps `detail.result` so the caller's
 *    onSuccess handler still receives a ReloadResult (with ok=false)
 *    -- structural failures stay on the success path so the toast UI
 *    can render the typed errors inline rather than treating the
 *    response as a transport-level failure.
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
      const detail = (error as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      const status = (error as { response?: { status?: number } })?.response
        ?.status;

      // Surface 409 reload-in-progress with a stable, parseable shape so
      // the caller can branch on the code without inspecting status codes.
      if (
        detail &&
        typeof detail === "object" &&
        (detail as ReloadInProgressDetail).code === "reload-in-progress"
      ) {
        const inProgress = detail as ReloadInProgressDetail;
        throw new Error(`reload-in-progress: ${inProgress.message}`);
      }

      // 422 carries the full ReloadResult in detail.result so structural
      // failures keep the same body shape as a 200 -- the caller's
      // onSuccess handler renders the typed errors inline via the
      // existing ok=false branch.
      if (status === 422 && detail && typeof detail === "object") {
        const result = (detail as { result?: ReloadBundleResponse }).result;
        if (result && typeof result === "object") {
          return result;
        }
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
