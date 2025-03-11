import { GRADIENT_CLASS_DISABLED } from "@/constants/constants";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useMemo, useRef, useState } from "react";
import { cn } from "../../../../../utils/utils";
import IconComponent from "../../../../common/genericIconComponent";
import { Input } from "../../../../ui/input";
import { InputProps, TextAreaComponentType } from "../../types";

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

export default function CopyFieldAreaComponent({
  value,
  handleOnNewValue,
  editNode = false,
  id = "",
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const isValueToReplace = value === BACKEND_URL;
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const endpointName = currentFlow?.endpoint_name ?? "";

  const valueToRender = useMemo(() => {
    if (isValueToReplace) {
      const urlWebhook = `${URL_WEBHOOK}${endpointName}`;
      return isValueToReplace ? urlWebhook : value;
    }
    return value;
  }, [value, endpointName]);

  const getInputClassName = () => {
    return cn(
      inputClasses.base({ isFocused }),
      editNode ? inputClasses.editNode : inputClasses.normal({ isFocused }),
      isFocused && "pr-10",
    );
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleOnNewValue({ value: e.target.value });
  };

  const handleCopy = (event?: React.MouseEvent<HTMLDivElement>) => {
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
    navigator.clipboard.writeText(valueToRender);

    setSuccessData({
      title: "Endpoint URL copied",
    });

    event?.stopPropagation();
  };

  const renderIcon = () => (
    <>
      {!isFocused && (
        <div
          className={cn(
            externalLinkIconClasses.gradient({
              editNode,
              disabled: false,
            }),
            editNode
              ? externalLinkIconClasses.editNodeTop
              : externalLinkIconClasses.normalTop,
          )}
          style={{
            pointerEvents: "none",
            background: isFocused ? undefined : GRADIENT_CLASS_DISABLED,
          }}
          aria-hidden="true"
        />
      )}
      <div onClick={handleCopy}>
        <IconComponent
          dataTestId={`btn_copy_${id?.toLowerCase()}${editNode ? "_advanced" : ""}`}
          name={isCopied ? "Check" : "Copy"}
          className={cn(
            "cursor-pointer bg-muted",
            externalLinkIconClasses.icon,
            editNode
              ? externalLinkIconClasses.editNodeTop
              : externalLinkIconClasses.iconTop,
            "bg-muted text-foreground",
          )}
        />
      </div>
    </>
  );

  return (
    <div className={cn("w-full")}>
      <Input
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        id={id}
        data-testid={id}
        value={valueToRender}
        onChange={handleInputChange}
        className={cn(getInputClassName())}
        aria-label={valueToRender}
        ref={inputRef}
        type="text"
        disabled
      />
      <div className="relative w-full">{renderIcon()}</div>
    </div>
  );
}
