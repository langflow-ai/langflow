import { TweaksComponent } from "@/components/core/codeTabsComponent/components/tweaksComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CustomAPIGenerator } from "@/customization/components/custom-api-generator";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import { ReactNode, useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import { useTweaksStore } from "../../stores/tweaksStore";
import BaseModal from "../baseModal";
import APITabsComponent from "./codeTabs/code-tabs";

export default function ApiModal({
  children,
  open: myOpen,
  setOpen: mySetOpen,
}: {
  children: ReactNode;
  open?: boolean;
  setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
}) {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const nodes = useFlowStore((state) => state.nodes);
  const [openTweaks, setOpenTweaks] = useState(false);
  const tweaks = useTweaksStore((state) => state.tweaks);
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);
  const newInitialSetup = useTweaksStore((state) => state.newInitialSetup);

  useEffect(() => {
    if (open) newInitialSetup(nodes);
  }, [open]);

  return (
    <>
      <BaseModal
        closeButtonClassName="!top-3"
        open={open}
        setOpen={setOpen}
        size="medium"
        className="pt-4"
      >
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
          {nodes.length > 0 && (
            <div className="border-r-1 absolute right-12 flex items-center text-[13px] font-medium leading-[16px]">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 px-3"
                onClick={() => setOpenTweaks(true)}
                data-testid="tweaks-button"
              >
                <IconComponent
                  name="SlidersHorizontal"
                  className="h-3.5 w-3.5"
                />
                <span>Tweaks ({Object.keys(tweaks)?.length}) </span>
              </Button>
              <Separator orientation="vertical" className="ml-2 h-8" />
            </div>
          )}
        </BaseModal.Header>
        <BaseModal.Content overflowHidden>
          {open && (
            <>
              <CustomAPIGenerator isOpen={open} />
              <APITabsComponent />
            </>
          )}
        </BaseModal.Content>
      </BaseModal>

      <BaseModal
        open={openTweaks}
        setOpen={setOpenTweaks}
        size="medium-small-tall"
      >
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
            name="SlidersHorizontal"
            className="h-6 w-6 text-gray-800 dark:text-white"
          />
          <span className="pl-2">Tweaks</span>
        </BaseModal.Header>
        <BaseModal.Content overflowHidden>
          <div className="h-full w-full overflow-y-auto overflow-x-hidden rounded-lg bg-muted custom-scroll">
            <TweaksComponent open={openTweaks} />
          </div>
        </BaseModal.Content>
      </BaseModal>
    </>
  );
}
