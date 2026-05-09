import { type MouseEvent, memo, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type {
  ExtensionErrorPayload,
  ReloadBundleResponse,
} from "@/controllers/API/queries/extensions";
import { useReloadBundle } from "@/controllers/API/queries/extensions";
import { ENABLE_EXTENSION_RELOAD } from "@/customization/feature-flags";
import useAlertStore from "@/stores/alertStore";
import { useUtilityStore } from "@/stores/utilityStore";

type AlertList = { title: string; list: string[] } | undefined;

/**
 * Render a list of typed errors / warnings into the alert-store list shape.
 *
 * The UI shows the first sentence (code + message) plus the hint indented;
 * keeping the hint in the same alert means the user does not need to dig
 * for the fix when a reload fails.  Returns ``undefined`` when the input
 * list is empty so the alert store does not render an empty bullet list.
 */
function renderTypedErrorList(
  payloads: readonly ExtensionErrorPayload[],
): AlertList {
  if (payloads.length === 0) {
    return undefined;
  }
  const list = payloads.flatMap((p) => {
    const lines: string[] = [`[${p.code}] ${p.message}`];
    if (p.hint) {
      lines.push(`  ${p.hint}`);
    }
    return lines;
  });
  return { title: "Reload diagnostics", list };
}

interface BundleHeaderActionsProps {
  bundleName: string;
  /**
   * Distribution id this bundle was installed from.  When undefined the
   * component renders nothing -- the Reload action requires both halves
   * of the registry coordinate so a click cannot 404 on the user.
   */
  extensionId: string | undefined;
  displayName: string;
}

/**
 * Overflow trigger ("⋮") next to the Bundle header chevron, plus the
 * matching context-menu wiring (the bundleItems wrapper handles the
 * right-click capture and forwards "reload" through this component's
 * Select).  Pure UI -- network / toast logic lives here so the parent
 * does not have to import ``useReloadBundle``.
 */
const BundleHeaderActionsInner = ({
  bundleName,
  extensionId,
  displayName,
}: BundleHeaderActionsProps) => {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const { mutate: reloadBundle, isPending } = useReloadBundle({
    onSuccess: (data: ReloadBundleResponse) => {
      // Two success-path shapes per the reload endpoint contract:
      //   1) ok=true: clean reload, components_added/removed describe the
      //      delta.  Show a green toast.
      //   2) ok=false: the pipeline ran but rejected the new source
      //      (broken module, name mismatch, missing path).  Show a red
      //      toast with the typed errors + hints inline.
      if (data.ok) {
        const added = data.components_added.length;
        const removed = data.components_removed.length;
        const summary =
          added === 0 && removed === 0
            ? t("sidebar.bundles.reload.success.noChanges", {
                bundle: displayName,
                defaultValue: "Reloaded {{bundle}} (no component changes)",
              })
            : t("sidebar.bundles.reload.success.withChanges", {
                bundle: displayName,
                added,
                removed,
                defaultValue:
                  "Reloaded {{bundle}} (+{{added}} / -{{removed}} components)",
              });
        const list = renderTypedErrorList(data.warnings);
        setSuccessData({
          title: summary,
          ...(list ? { list: list.list } : {}),
        });
        return;
      }
      const list = renderTypedErrorList(data.errors);
      setErrorData({
        title: t("sidebar.bundles.reload.failure.structural", {
          bundle: displayName,
          defaultValue: "Reload failed for {{bundle}}",
        }),
        ...(list ? { list: list.list } : {}),
      });
    },
    onError: (error: Error) => {
      const message = error?.message ?? "";
      // The 409 case (reload-in-progress) is informational, not a hard
      // failure: another tab / worker is already swapping the same bundle.
      // Use the notice toast so the user gets feedback without alarming
      // red styling.
      if (message.startsWith("reload-in-progress:")) {
        setNoticeData({
          title: t("sidebar.bundles.reload.inProgress", {
            bundle: displayName,
            defaultValue: "Reload already in progress for {{bundle}}",
          }),
        });
        return;
      }
      setErrorData({
        title: t("sidebar.bundles.reload.failure.network", {
          bundle: displayName,
          defaultValue: "Could not reload {{bundle}}",
        }),
        list: [message || "Unknown error"],
      });
    },
  });

  // Reload is an action -- not a selection -- so wire it via DropdownMenuItem's
  // onSelect callback.  Radix's Select primitive (the previous wiring) is
  // for *value* selection: it gates ``onValueChange`` on value-equality and
  // its popover-portal click semantics interact poorly with the parent
  // disclosure-trigger button, which together swallow the click and prevent
  // the network request from ever firing.  DropdownMenu is purpose-built
  // for action menus and fires onSelect on every activation.
  const handleReload = useCallback(() => {
    if (!extensionId) return;
    reloadBundle({ extensionId, bundleName });
  }, [extensionId, bundleName, reloadBundle]);

  // Stop propagation so opening the menu / clicking Reload does not also
  // collapse / expand the parent disclosure trigger.
  const stopPropagation = useCallback(
    (event: MouseEvent<HTMLButtonElement | HTMLDivElement>) => {
      event.stopPropagation();
    },
    [],
  );

  // Defense-in-depth gate: parents already check both flags but a future
  // caller that bypasses BundleItem / CategoryDisclosure must not surface
  // the action against a backend that has reload disabled.
  const enableReloadRuntime = useUtilityStore(
    (state) => state.enableExtensionReload,
  );
  const visible = useMemo(
    () =>
      ENABLE_EXTENSION_RELOAD && enableReloadRuntime && Boolean(extensionId),
    [enableReloadRuntime, extensionId],
  );

  if (!visible) {
    return null;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        tabIndex={-1}
        onClick={stopPropagation}
        className="flex h-6 w-6 items-center justify-center rounded border-0 p-0 shadow-none outline-none focus:ring-0"
        data-testid={`bundle-header-overflow-${bundleName}`}
        aria-label={t("sidebar.bundles.reload.overflowAria", {
          bundle: displayName,
          defaultValue: "Open actions for {{bundle}}",
        })}
      >
        <ForwardedIconComponent
          name={isPending ? "Loader2" : "MoreHorizontal"}
          className={
            isPending
              ? "h-4 w-4 animate-spin text-muted-foreground"
              : "h-4 w-4 text-muted-foreground"
          }
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" align="end" onClick={stopPropagation}>
        <DropdownMenuItem
          disabled={isPending}
          onSelect={handleReload}
          data-testid={`bundle-header-reload-${bundleName}`}
        >
          <ForwardedIconComponent name="RefreshCw" className="mr-2 h-4 w-4" />
          {t("sidebar.bundles.reload.action", {
            defaultValue: "Reload",
          })}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const BundleHeaderActions = memo(BundleHeaderActionsInner);
BundleHeaderActions.displayName = "BundleHeaderActions";

export default BundleHeaderActions;
