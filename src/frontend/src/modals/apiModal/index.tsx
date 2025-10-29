import { Button } from "@/components/ui/button";
import { CustomAPIGenerator } from "@/customization/components/custom-api-generator";
import { CustomLink } from "@/customization/components/custom-link";
import useFlowStore from "@/stores/flowStore";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import { type ReactNode, useEffect, useState } from "react";
import { useShallow } from "zustand/react/shallow";
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
  const nodes = useFlowStore((state) => state.nodes);
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);
  const initialSetup = useTweaksStore((state) => state.initialSetup);

  const currentFlowId = useFlowStore(
    useShallow((state) => state.currentFlow?.id),
  );

  useEffect(() => {
    if (open && currentFlowId) initialSetup(nodes, currentFlowId);
  }, [open]);

  return (
    <BaseModal
      closeButtonClassName="!top-3"
      open={open}
      setOpen={setOpen}
      size="x-large"
      className="pt-4"
    >
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header
        description={
          <span className="pr-2">
            API access requires an API key. You can{" "}
            <CustomLink
              to="/settings/api-keys"
              className="text-accent-pink-foreground"
            >
              {" "}
              create an API key
            </CustomLink>{" "}
            in settings.
          </span>
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
            <APITabsComponent />
          </>
        )}
      </BaseModal.Content>
    </BaseModal>
  );
}
