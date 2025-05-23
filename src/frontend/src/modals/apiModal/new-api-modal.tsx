import { TweaksComponent } from "@/components/core/codeTabsComponent/components/tweaksComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { CustomAPIGenerator } from "@/customization/components/custom-api-generator";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useAuthStore from "@/stores/authStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { isEndpointNameValid } from "@/utils/utils";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import { cloneDeep } from "lodash";
import { ChangeEvent, ReactNode, useEffect, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import IconComponent from "../../components/common/genericIconComponent";
import { useTweaksStore } from "../../stores/tweaksStore";
import BaseModal from "../baseModal";
import APITabsComponent from "./codeTabs/code-tabs";

const MAX_LENGTH = 20;
const MIN_LENGTH = 1;

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

  const flowEndpointName = useFlowStore(
    useShallow((state) => state.currentFlow?.endpoint_name),
  );

  const [endpointName, setEndpointName] = useState(flowEndpointName ?? "");
  const [validEndpointName, setValidEndpointName] = useState(true);

  const handleEndpointNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    // Validate the endpoint name
    // use this regex r'^[a-zA-Z0-9_-]+$'
    const isValid = isEndpointNameValid(event.target.value, MAX_LENGTH);
    setValidEndpointName(isValid);

    // Only update if valid and meets minimum length (if set)
    if (isValid && value.length >= MIN_LENGTH) {
      setEndpointName!(value);
    } else if (value.length === 0) {
      // Always allow empty endpoint name (it's optional)
      setEndpointName!("");
    }
  };

  useEffect(() => {
    if (open) newInitialSetup(nodes);
  }, [open]);

  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const saveFlow = useSaveFlow();
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);

  function handleSave(): void {
    const newFlow = cloneDeep(useFlowStore.getState().currentFlow);
    if (!newFlow) return;
    newFlow.endpoint_name =
      endpointName && endpointName.length > 0 ? endpointName : null;

    if (autoSaving) {
      saveFlow(newFlow);
    } else {
      setCurrentFlow(newFlow);
    }
  }

  useEffect(() => {
    if (!openTweaks && endpointName !== flowEndpointName) handleSave();
    else if (openTweaks) {
      setEndpointName(flowEndpointName ?? "");
    }
  }, [openTweaks]);

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
            <div className="border-r-1 absolute right-12 flex items-center text-mmd font-medium leading-[16px]">
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
        <BaseModal.Content overflowHidden className="flex flex-col gap-4">
          {true && (
            <Label>
              <div className="edit-flow-arrangement mt-2">
                <span className="shrink-0 text-mmd font-medium">
                  Endpoint Name
                </span>
                {!validEndpointName && (
                  <span className="edit-flow-span">
                    Use only letters, numbers, hyphens, and underscores (
                    {MAX_LENGTH} characters max).
                  </span>
                )}
              </div>
              <Input
                className="nopan nodelete nodrag noflow mt-2 font-normal"
                onChange={handleEndpointNameChange}
                type="text"
                name="endpoint_name"
                value={endpointName ?? ""}
                placeholder="An alternative name to run the endpoint"
                maxLength={MAX_LENGTH}
                minLength={MIN_LENGTH}
                id="endpoint_name"
              />
            </Label>
          )}
          <div className="h-full w-full overflow-y-auto overflow-x-hidden rounded-lg bg-muted custom-scroll">
            <TweaksComponent open={openTweaks} />
          </div>
        </BaseModal.Content>
      </BaseModal>
    </>
  );
}
