import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/controllers/API/api";
import { BASE_URL_API, PROXY_TARGET } from "@/customization/config-constants";
import useFlowStore from "@/stores/flowStore";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import { ReactNode, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import IconComponent from "../../components/common/genericIconComponent";
import BaseModal from "../baseModal";
import { ApiKeyGenerator } from "./components/apiKeyGenerator";
import { CopyInput } from "./components/copyInput";

export default function NvidiaR2xModal({
  children,
  open: myOpen,
  setOpen: mySetOpen,
}: {
  children?: ReactNode;
  open?: boolean;
  setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
}) {
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);

  const host = api.defaults.baseURL || window.location.origin;

  const hostName = host.split("://")[1].split(":")[0];
  const portNumber = host.split("://")[1].split(":")[1].split("/")[0];

  const { flowId, flowName } = useFlowStore(
    useShallow((state) => ({
      flowName: state.currentFlow?.name,
      flowId: state.currentFlow?.id,
    })),
  );

  const endpointUrl = `${BASE_URL_API}ws/flow_as_tool/${flowId}`;

  return (
    <>
      <BaseModal
        open={open}
        setOpen={setOpen}
        size="small-h-full"
        className="p-4"
      >
        <BaseModal.Trigger asChild>{children ?? <></>}</BaseModal.Trigger>
        <BaseModal.Header description="Here's some instructions to connect with NVIDIA R2X. You'll need your Flow ID, your Port Number, and an API key.">
          <IconComponent
            name="Mic"
            className="h-5 w-5 text-muted-foreground"
            aria-hidden="true"
          />
          <span className="pl-1.5">NVIDIA Project R2X</span>
        </BaseModal.Header>
        <BaseModal.Content overflowHidden>
          <div className="flex flex-col gap-4">
            <CopyInput value={hostName} label="Host Name" />
            <CopyInput value={portNumber} label="Port Number" />
            <CopyInput value={endpointUrl} label="Endpoint URL" />
            <ApiKeyGenerator flowName={flowName ?? ""} />
          </div>
        </BaseModal.Content>
      </BaseModal>
    </>
  );
}
