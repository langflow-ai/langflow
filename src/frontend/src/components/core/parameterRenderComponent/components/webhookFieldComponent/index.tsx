import { Button } from "@/components/ui/button";
import { GRADIENT_CLASS } from "@/constants/constants";
import { track } from "@/customization/utils/analytics";
import { getCurlWebhookCode } from "@/modals/apiModal/utils/get-curl-code";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import { useMemo, useRef, useState } from "react";
import { cn } from "../../../../../utils/utils";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../common/genericIconComponent";
import { Input } from "../../../../ui/input";
import { InputProps, TextAreaComponentType } from "../../types";
import CopyFieldAreaComponent from "../copyFieldAreaComponent";

const BACKEND_URL = "BACKEND_URL";
const URL_WEBHOOK = `${window.location.protocol}//${window.location.host}/api/v1/webhook/`;

const inputClasses = {
  base: ({ isFocused }: { isFocused: boolean }) =>
    `w-full ${isFocused ? "" : "pr-3"}`,
  editNode: "input-edit-node",
  normal: ({ isFocused }: { isFocused: boolean }) =>
    `primary-input ${isFocused ? "text-primary" : "text-muted-foreground"}`,
  disabled: "disabled-state",
};

const externalLinkIconClasses = {
  gradient: ({
    editNode,
    disabled,
  }: {
    editNode: boolean;
    disabled: boolean;
  }) =>
    disabled
      ? "gradient-fade-input-edit-node"
      : editNode
        ? "gradient-fade-input-edit-node"
        : "gradient-fade-input",
  background: ({
    editNode,
    disabled,
  }: {
    editNode: boolean;
    disabled: boolean;
  }) =>
    disabled
      ? ""
      : editNode
        ? "background-fade-input-edit-node"
        : "background-fade-input",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0",
  editNodeTop: "top-[-1.4rem] h-5",
  normalTop: "top-[-2.1rem] h-7",
  iconTop: "top-[-1.7rem]",
};

export default function WebhookFieldComponent({
  value,
  handleOnNewValue,
  editNode = false,
  id = "",
  nodeInformationMetadata,
  ...baseInputProps
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  return (
    <div className="grid w-full gap-2">
      <div>
        <CopyFieldAreaComponent
          id={id}
          value={value}
          editNode={editNode}
          handleOnNewValue={handleOnNewValue}
          {...baseInputProps}
        />
      </div>
      <div>
        <Button
          size="sm"
          data-testid="generate_token_webhook_button"
          variant="outline"
        >
          <ForwardedIconComponent name="Key" className="h-4 w-4" />
          Generate token
        </Button>
      </div>
    </div>
  );
}
