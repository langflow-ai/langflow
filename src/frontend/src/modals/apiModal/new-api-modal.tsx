import { CustomAPIGenerator } from "@/customization/components/custom-api-generator";
import { useCustomAPICode } from "@/customization/hooks/use-custom-api-code";
import useAuthStore from "@/stores/authStore";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import { ReactNode, useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import { EXPORT_CODE_DIALOG } from "../../constants/constants";
import { useTweaksStore } from "../../stores/tweaksStore";
import { FlowType } from "../../types/flow/index";
import BaseModal from "../baseModal";
import APITabsComponent from "./codeTabs/code-tabs";

export default function ApiModal({
  flow,
  children,
  open: myOpen,
  setOpen: mySetOpen,
}: {
  flow: FlowType;
  children: ReactNode;
  open?: boolean;
  setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
}) {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);
  const [activeTab, setActiveTab] = useState("0");
  const activeTweaks = useTweaksStore((state) => state.activeTweaks);
  const setActiveTweaks = useTweaksStore((state) => state.setActiveTweaks);
  const tabs = useTweaksStore((state) => state.tabs);
  const initialSetup = useTweaksStore((state) => state.initialSetup);

  const getCodes = useCustomAPICode();

  useEffect(() => {
    if (open) initialSetup(autoLogin ?? false, flow, getCodes);
    setActiveTab("0");
  }, [open]);

  return (
    <BaseModal open={open} setOpen={setOpen} size="medium">
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header
        description={
          autoLogin ? undefined : (
            <>
              <span className="pr-2">
                API access requires an API key. You can{" "}
                <a
                  href="/settings/api-keys"
                  className="text-accent-pink-foreground"
                >
                  {" "}
                  create an API key
                </a>{" "}
                in settings.
              </span>
            </>
          )
        }
      >
        <IconComponent
          name="Code2"
          className="h-6 w-6 text-gray-800 dark:text-white"
          aria-hidden="true"
        />
        <span className="pl-2">API access</span>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        {open && (
          <>
            <CustomAPIGenerator isOpen={open} />
            <APITabsComponent
              open={open}
              activeTweaks={activeTweaks}
              setActiveTweaks={setActiveTweaks}
            />
          </>
        )}
      </BaseModal.Content>
    </BaseModal>
  );
}
