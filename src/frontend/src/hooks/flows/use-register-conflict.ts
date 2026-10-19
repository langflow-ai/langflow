import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import type { ConflictDetail } from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import {
  attachTheirFlow,
  fetchAndAdoptServerVersion,
  registerConflictState,
} from "./conflict-actions";

/**
 * Handle a graph write the server refused because someone saved first: a save,
 * or a restore from the flow's history.
 */
export default function useRegisterConflict() {
  const { t } = useTranslation();
  const setNoticeData = useAlertStore((state) => state.setNoticeData);

  return useCallback(
    (flowId: string, detail: ConflictDetail) => {
      const currentUserId = useAuthStore.getState().userData?.id ?? null;
      const authorId = detail.modified_by?.id ?? null;
      const authorName = detail.modified_by?.username ?? null;

      // Nothing of mine is on the canvas, so there is nothing to resolve. Raising a
      // banner here produced a dialog with no changes on either side and no honest
      // exit; taking their version is the whole answer. It is said out loud, because
      // the refused request still carried something the person typed -- a rename, a
      // lock, an endpoint -- and adopting their version drops it. That used to
      // disappear with no message at all.
      if (!useFlowStore.getState().userEditedSinceLoad) {
        setNoticeData({
          title: authorName
            ? t("multiEdit.notice.changeNotApplied", { name: authorName })
            : t("multiEdit.notice.changeNotAppliedUnknown"),
        });
        void fetchAndAdoptServerVersion(flowId);
        return;
      }
      // Registering also persists the draft, so refused work survives a reload no
      // matter which path noticed the conflict.
      registerConflictState({
        flowId,
        authorId,
        authorName,
        modifiedAt: detail.modified_at ?? null,
        expectedToken: detail.expected_version_token ?? null,
        currentToken: detail.current_version_token ?? null,
        currentUserId,
      });

      // Fetched now, not when the dialog opens: a third save in between would make
      // the diff describe a version this conflict was never about.
      void attachTheirFlow(flowId);
    },
    [t, setNoticeData],
  );
}

/**
 * The `If-Match` header for a write built on the version the editor last
 * loaded or saved, so the server refuses it when someone saved after that.
 */
export const reviewedVersionHeaders = (
  flowId: string,
): Record<string, string> | undefined => {
  const baseline = useFlowsManagerStore.getState().currentFlow;
  const token = baseline?.id === flowId ? baseline.version_token : null;
  return token ? { "If-Match": token } : undefined;
};
