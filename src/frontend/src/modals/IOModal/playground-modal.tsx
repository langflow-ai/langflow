//import LangflowLogoColor from "@/assets/LangflowLogocolor.svg?react";

import { useCallback, useEffect, useRef, useState } from "react";
import { v5 as uuidv5 } from "uuid";
import { useShallow } from "zustand/react/shallow";
import ThemeButtons from "@/components/core/appHeaderComponent/components/ThemeButtons";
import { PlaygroundComponent } from "@/components/core/playgroundComponent/playground-component";
import {
  useDeleteMessages,
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { track } from "@/customization/utils/analytics";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import { LangflowButtonRedirectTarget } from "@/customization/utils/urls";
import { useUtilityStore } from "@/stores/utilityStore";
import { swatchColors } from "@/utils/styleUtils";
import LangflowLogoColor from "../../assets/LangflowLogoColor.svg?react";
import IconComponent from "../../components/common/genericIconComponent";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { ChatViewWrapper } from "../../components/core/playgroundComponent/components/chat-view-wrapper";
import { createNewSessionName } from "../../components/core/playgroundComponent/components/chatView/chatInput/components/voice-assistant/helpers/create-new-session-name";
import { SelectedViewField } from "../../components/core/playgroundComponent/components/selected-view-field";
import { SidebarOpenView } from "../../components/core/playgroundComponent/components/sidebar-open-view";
import { Button } from "../../components/ui/button";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import type { IOModalPropsType } from "../../types/components";
import { cn, getNumberFromString } from "../../utils/utils";
import BaseModal from "../baseModal";

export default function IOModal({
  children,
  open,
  setOpen,
  disable,
  isPlayground,
}: IOModalPropsType): JSX.Element {
  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      disable={disable}
      type={isPlayground ? "full-screen" : undefined}
      size="x-large"
      className="!rounded-[12px] p-0"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Content overflowHidden className="h-full">
        {open && <PlaygroundComponent />}
      </BaseModal.Content>
    </BaseModal>
  );
}
