import FlowSettingsComponent from "@/components/core/flowSettingsComponent";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import EditFlowSettings from "../../components/core/editFlowSettingsComponent";
import { SETTINGS_DIALOG_SUBTITLE } from "../../constants/constants";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowSettingsPropsType } from "../../types/components";
import { FlowType } from "../../types/flow";
import { isEndpointNameValid } from "../../utils/utils";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
  flowData,
  details,
}: FlowSettingsPropsType): JSX.Element {
  if (!open) return <></>;
  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="small-update"
      className="p-4"
    >
      <BaseModal.Header>
        <span className="text-base font-semibold">Flow Details</span>
      </BaseModal.Header>
      <BaseModal.Content>
        <FlowSettingsComponent
          flowData={flowData}
          details={details}
          close={() => setOpen(false)}
        />
      </BaseModal.Content>
    </BaseModal>
  );
}
