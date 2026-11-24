import { Outlet } from "react-router-dom";
import { ChangesPausedNotice } from "@/components/common/changesPausedNotice";
import { StorageUpgradeNotice } from "@/components/common/storageUpgradeNotice";
import { ExtensionEventsListener } from "@/components/extensions/ExtensionEventsListener";
import { ENABLE_EXTENSION_RELOAD } from "@/customization/feature-flags";
import { useCustomPostAuth } from "@/customization/hooks/use-custom-post-auth";
import { useUtilityStore } from "@/stores/utilityStore";

export function AppAuthenticatedPage() {
  useCustomPostAuth();
  const enableExtensionReloadRuntime = useUtilityStore(
    (state) => state.enableExtensionReload,
  );
  const extensionsEnabled =
    ENABLE_EXTENSION_RELOAD && enableExtensionReloadRuntime;

  return (
    <>
      {extensionsEnabled && <ExtensionEventsListener />}
      <StorageUpgradeNotice />
      <Outlet />
      {/* After the page, so it shows above the editor's sidebar, which sits at the same level. */}
      <ChangesPausedNotice />
    </>
  );
}
