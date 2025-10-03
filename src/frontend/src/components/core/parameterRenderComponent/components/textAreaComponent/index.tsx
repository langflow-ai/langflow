import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GRADIENT_CLASS } from "@/constants/constants";
import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { getCurlWebhookCode } from "@/modals/apiModal/utils/get-curl-code";
import ComponentTextModal from "@/modals/textAreaModal";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "../../../../../utils/utils";
import IconComponent from "../../../../common/genericIconComponent";
import { Input } from "../../../../ui/input";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputProps, TextAreaComponentType } from "../../types";
import { getIconName } from "../inputComponent/components/helpers/get-icon-name";

const inputClasses = {
  base: ({ isFocused, password }: { isFocused: boolean; password: boolean }) =>
    `w-full ${isFocused ? "" : "pr-3"} ${password ? "pr-16" : ""}`,
  editNode: "input-edit-node",
  normal: ({ isFocused }: { isFocused: boolean }) =>
    `primary-input ${isFocused ? "text-primary" : "text-muted-foreground"}`,
  disabled: "disabled-state",
  password: "password",
};

const WEBHOOK_VALUE = "CURL_WEBHOOK";
const MCP_SSE_VALUE = "MCP_SSE";

const { protocol, host } = customGetHostProtocol();
const URL_MCP_SSE = `${protocol}//${host}/api/v1/mcp/sse`;

const externalLinkIconClasses = {
  gradient: ({
    disabled,
    editNode,
    password,
  }: {
    disabled: boolean;
    editNode: boolean;
    password: boolean;
  }) =>
    disabled || password
      ? ""
      : editNode
        ? "gradient-fade-input-edit-node"
        : "gradient-fade-input",
  background: ({
    disabled,
    editNode,
  }: {
    disabled: boolean;
    editNode: boolean;
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

export default function TextAreaComponent({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
  updateVisibility,
  password,
  placeholder,
  isToolMode = false,
  nodeInformationMetadata,
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const webhookAuthEnable = useUtilityStore((state) => state.webhookAuthEnable);
  const [cursor, setCursor] = useState<number | null>(null);

  // --- IME handling ---
  const [localValue, setLocalValue] = useState<string>(value ?? "");
  const [isComposing, setIsComposing] = useState(false);

  useEffect(() => {
    if (!isComposing) setLocalValue(value ?? "");
  }, [value, isComposing]);

  const normalizeNFC = useCallback((v: string) => {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    return typeof v?.normalize === "function" ? v.normalize("NFC") : v;
  }, []);

  const isWebhook = useMemo(
    () => nodeInformationMetadata?.nodeType === "webhook",
    [nodeInformationMetadata?.nodeType],
  );

  const _isMCPSSE = useMemo(
    () => nodeInformationMetadata?.nodeType === "mcp_sse",
    [nodeInformationMetadata?.nodeType],
  );

  useEffect(() => {
    if (isWebhook && value === WEBHOOK_VALUE) {
      const curlWebhookCode = getCurlWebhookCode({
        flowId: nodeInformationMetadata?.flowId!,
        webhookAuthEnable,
        flowName: nodeInformationMetadata?.flowName!,
        format: "singleline",
      });
      handleOnNewValue({ value: curlWebhookCode });
    } else if (value === MCP_SSE_VALUE) {
      const mcpSSEUrl = `${URL_MCP_SSE}`;
      handleOnNewValue({ value: mcpSSEUrl });
    }
  }, [
    isWebhook,
    value,
    nodeInformationMetadata,
    handleOnNewValue,
    webhookAuthEnable,
  ]);

  useEffect(() => {
    if (cursor !== null && inputRef.current) {
      inputRef.current.setSelectionRange(cursor, cursor);
    }
  }, [cursor, localValue]);

  const getInputClassName = () => {
    return cn(
      inputClasses.base({ isFocused, password: password! }),
      editNode ? inputClasses.editNode : inputClasses.normal({ isFocused }),
      disabled && inputClasses.disabled,
      password && !passwordVisible && "text-clip",
      isFocused && "pr-10",
    );
  };

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = e.target.value;
      setLocalValue(v);
      setCursor(e.target.selectionStart);

      // cobre a maioria dos casos (especialmente Linux/IBus)
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      const nativeIsComposing = !!e.nativeEvent?.isComposing;
      if (isComposing || nativeIsComposing) return;

      handleOnNewValue({ value: normalizeNFC(v) });
    },
    [handleOnNewValue, isComposing, normalizeNFC],
  );

  const handleCompositionStart = useCallback(() => {
    setIsComposing(true);
  }, []);

  const handleCompositionEnd = useCallback(
    (e: React.CompositionEvent<HTMLInputElement>) => {
      setIsComposing(false);
      const finalV = normalizeNFC(e.currentTarget.value ?? "");
      setLocalValue(finalV);
      handleOnNewValue({ value: finalV });
    },
    [handleOnNewValue, normalizeNFC],
  );

  const changeWebhookFormat = (format: "multiline" | "singleline") => {
    if (isWebhook) {
      const curlWebhookCode = getCurlWebhookCode({
        flowId: nodeInformationMetadata?.flowId!,
        webhookAuthEnable,
        flowName: nodeInformationMetadata?.flowName!,
        format,
      });
      handleOnNewValue({ value: curlWebhookCode });
    }
  };

  const renderIcon = () => (
    <div>
      {!disabled && !isFocused && (
        <div
          className={cn(
            externalLinkIconClasses.gradient({
              disabled,
              editNode,
              password: password!,
            }),
            editNode
              ? externalLinkIconClasses.editNodeTop
              : externalLinkIconClasses.normalTop,
          )}
          style={{
            pointerEvents: "none",
            background: isFocused
              ? undefined
              : disabled
                ? "bg-background"
                : GRADIENT_CLASS,
          }}
          aria-hidden="true"
        />
      )}

      <IconComponent
        dataTestId={`button_open_text_area_modal_${id}${
          editNode ? "_advanced" : ""
        }`}
        name={getIconName(disabled, "", "", false, isToolMode) || "Scan"}
        className={cn(
          "cursor-pointer bg-background",
          externalLinkIconClasses.icon,
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.iconTop,
          disabled
            ? "bg-muted text-placeholder-foreground"
            : "bg-background text-foreground",
        )}
      />
    </div>
  );

  return (
    <div className={cn("w-full", disabled && "pointer-events-none")}>
      <Input
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        id={id}
        data-testid={id}
        value={disabled ? "" : localValue}
        onChange={handleChange}
        onCompositionStart={handleCompositionStart}
        onCompositionEnd={handleCompositionEnd}
        disabled={disabled}
        className={getInputClassName()}
        placeholder={getPlaceholder(disabled, placeholder)}
        aria-label={disabled ? localValue : undefined}
        ref={inputRef}
        type={password ? (passwordVisible ? "text" : "password") : "text"}
        readOnly={isWebhook}
      />

      <ComponentTextModal
        changeVisibility={updateVisibility}
        value={localValue}
        setValue={(newValue) => {
          const nv = normalizeNFC(newValue ?? "");
          setLocalValue(nv);
          handleOnNewValue({ value: nv });
        }}
        disabled={disabled}
        onCloseModal={() => changeWebhookFormat("singleline")}
      >
        <div
          onClick={() => changeWebhookFormat("multiline")}
          className="relative w-full"
        >
          {renderIcon()}
        </div>
      </ComponentTextModal>

      {password && !isFocused && (
        <div
          onClick={() => {
            setPasswordVisible(!passwordVisible);
          }}
        >
          <IconComponent
            name={passwordVisible ? "eye" : "eye-off"}
            className={cn(
              externalLinkIconClasses.icon,
              editNode ? "top-[5px]" : "top-[13px]",
              disabled
                ? "text-placeholder"
                : "text-placeholder-foreground hover:text-foreground",
              "right-10",
            )}
          />
        </div>
      )}
    </div>
  );
}
