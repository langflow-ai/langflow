import * as Form from "@radix-ui/react-form";
import { useCallback, useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import type { InputComponentType } from "@/types/components";
import { handleKeyDown } from "@/utils/reactflowUtils";
import { classNames, cn } from "@/utils/utils";
import { useIMEInput } from "../../hooks/use-ime-input";
import { getIconName } from "./components/helpers/get-icon-name";
import CustomInputPopover from "./components/popover";
import CustomInputPopoverObject from "./components/popoverObject";

interface FormInputBranchProps {
  refInput: React.RefObject<HTMLInputElement | null>;
  value: string;
  onChange?: (value: string, skipSnapshot?: boolean) => void;
  onChangeFolderName?: (e: {
    target: { value: string; selectionStart: number | null };
  }) => void;
  onInputLostFocus: (event: React.FocusEvent<HTMLInputElement>) => void;
  autoFocus: boolean;
  password?: boolean;
  pwdVisible: boolean;
  disabled?: boolean;
  required: boolean;
  editNode: boolean;
  className?: string;
  placeholder: string;
  blurOnEnter: boolean;
  name?: string;
  id: string;
}

function FormInputBranch({
  refInput,
  value,
  onChange,
  onChangeFolderName,
  onInputLostFocus,
  autoFocus,
  password,
  pwdVisible,
  disabled,
  required,
  editNode,
  className,
  placeholder,
  blurOnEnter,
  name,
  id,
}: FormInputBranchProps) {
  const [cursor, setCursor] = useState<number | null>(null);

  const commitValue = useCallback(
    (newValue: string) => {
      if (onChangeFolderName) {
        onChangeFolderName({
          target: {
            value: newValue,
            selectionStart: refInput.current?.selectionStart ?? null,
          },
        });
        return;
      }
      onChange?.(newValue);
    },
    [onChange, onChangeFolderName, refInput],
  );

  const {
    displayValue,
    inputProps: imeInputProps,
    flushPendingComposition,
  } = useIMEInput<HTMLInputElement>({
    value: value ?? "",
    onCommit: commitValue,
    inputRef: refInput,
    cursor,
    setCursor,
  });

  const handleBlur = (event: React.FocusEvent<HTMLInputElement>) => {
    flushPendingComposition();
    onInputLostFocus(event);
  };

  return (
    <Form.Control asChild>
      <Input
        name={name}
        id={"form-" + id}
        ref={refInput}
        autoFocus={autoFocus}
        type={password && !pwdVisible ? "password" : "text"}
        {...imeInputProps}
        onBlur={handleBlur}
        value={displayValue}
        disabled={disabled}
        required={required}
        className={classNames(
          password && !pwdVisible && value !== "" ? "text-clip password" : "",
          editNode ? "input-edit-node" : "",
          password && editNode ? "pr-8" : "",
          password && !editNode ? "pr-10" : "",
          className!,
        )}
        placeholder={password && editNode ? "Key" : placeholder}
        onCopy={(e) => {
          e.preventDefault();
        }}
        onKeyDown={(e) => {
          handleKeyDown(e, value, "");
          if (blurOnEnter && e.key === "Enter") refInput.current?.blur();
        }}
      />
    </Form.Control>
  );
}

export default function InputComponent({
  autoFocus = false,
  onBlur,
  value = "",
  onChange,
  disabled,
  required = false,
  isForm = false,
  password,
  editNode = false,
  placeholder = "Type something...",
  className,
  id = "",
  blurOnEnter = false,
  optionsIcon = "ChevronsUpDown",
  selectedOption,
  setSelectedOption,
  selectedOptions = [],
  setSelectedOptions,
  options = [],
  disabledOptions,
  optionsPlaceholder = "Search options...",
  optionsButton,
  optionButton,
  objectOptions,
  isObjectOption = false,
  name,
  onChangeFolderName,
  nodeStyle,
  isToolMode,
  popoverWidth,
  commandWidth,
  blockAddNewGlobalVariable = false,
  hasRefreshButton = false,
  inspectionPanel = false,
}: InputComponentType & {
  disabledOptions?: Record<string, string>;
}): JSX.Element {
  const [pwdVisible, setPwdVisible] = useState(false);
  const refInput = useRef<HTMLInputElement>(null);
  const [showOptions, setShowOptions] = useState<boolean>(false);

  useEffect(() => {
    if (disabled && value && onChange && value !== "") {
      onChange("", true);
    }
  }, [disabled]);

  function onInputLostFocus(event): void {
    if (onBlur) onBlur(event);
  }

  return (
    <div className="relative w-full">
      {isForm ? (
        <FormInputBranch
          refInput={refInput}
          value={value}
          onChange={onChange}
          onChangeFolderName={onChangeFolderName}
          onInputLostFocus={onInputLostFocus}
          autoFocus={autoFocus}
          password={password}
          pwdVisible={pwdVisible}
          disabled={disabled}
          required={required}
          editNode={editNode}
          className={className}
          placeholder={placeholder}
          blurOnEnter={blurOnEnter}
          name={name}
          id={id}
        />
      ) : (
        <>
          {isObjectOption ? (
            // Content to render when isObjectOption is true
            <CustomInputPopoverObject
              refInput={refInput}
              handleKeyDown={handleKeyDown}
              optionButton={optionButton}
              optionsButton={optionsButton}
              showOptions={showOptions}
              onChange={onChange}
              id={`object-${id}`}
              onInputLostFocus={onInputLostFocus}
              selectedOption={selectedOption}
              setSelectedOption={setSelectedOption}
              selectedOptions={selectedOptions}
              setSelectedOptions={setSelectedOptions}
              options={objectOptions}
              value={value}
              editNode={editNode}
              autoFocus={autoFocus}
              disabled={disabled}
              setShowOptions={setShowOptions}
              required={required}
              placeholder={placeholder}
              blurOnEnter={blurOnEnter}
              optionsPlaceholder={optionsPlaceholder}
              className={className}
              inspectionPanel={inspectionPanel}
            />
          ) : (
            <CustomInputPopover
              refInput={refInput}
              handleKeyDown={handleKeyDown}
              optionButton={optionButton}
              optionsButton={optionsButton}
              showOptions={showOptions}
              onChange={onChange}
              id={`popover-anchor-${id}`}
              onInputLostFocus={onInputLostFocus}
              selectedOption={selectedOption}
              setSelectedOption={setSelectedOption}
              selectedOptions={selectedOptions}
              setSelectedOptions={setSelectedOptions}
              value={value}
              autoFocus={autoFocus}
              disabled={disabled}
              setShowOptions={setShowOptions}
              required={required}
              password={password}
              pwdVisible={pwdVisible}
              editNode={editNode}
              placeholder={placeholder}
              blurOnEnter={blurOnEnter}
              options={options}
              disabledOptions={disabledOptions}
              optionsPlaceholder={optionsPlaceholder}
              nodeStyle={nodeStyle}
              popoverWidth={popoverWidth}
              commandWidth={commandWidth}
              blockAddNewGlobalVariable={blockAddNewGlobalVariable}
              hasRefreshButton={hasRefreshButton}
              inspectionPanel={inspectionPanel}
            />
          )}
        </>
      )}

      {(setSelectedOption || setSelectedOptions) &&
        !blockAddNewGlobalVariable && (
          <span
            className={cn(
              password && selectedOption === "" ? "right-8" : "right-0",
              "absolute inset-y-0 flex items-center pr-2.5",
              disabled && "cursor-not-allowed opacity-50",
            )}
          >
            <button
              disabled={disabled}
              onClick={(e) => {
                if (disabled) return;
                setShowOptions(!showOptions);
                e.preventDefault();
                e.stopPropagation();
              }}
              className={cn(
                onChange && setSelectedOption && selectedOption !== ""
                  ? "text-accent-emerald-foreground"
                  : "text-placeholder-foreground",
                !disabled && "hover:text-foreground",
              )}
            >
              <ForwardedIconComponent
                name={
                  getIconName(
                    disabled!,
                    selectedOption!,
                    optionsIcon,
                    nodeStyle!,
                    isToolMode!,
                  ) || "ChevronsUpDown"
                }
                className={cn(
                  disabled ? "cursor-grab text-placeholder" : "cursor-pointer",
                  "icon-size",
                )}
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden="true"
              />
            </button>
          </span>
        )}

      {password && (!setSelectedOption || selectedOption === "") && (
        <button
          type="button"
          tabIndex={-1}
          className={classNames(
            "mb-px mr-3 p-0",
            editNode
              ? "input-component-true-button"
              : "input-component-false-button",
          )}
          onClick={(event) => {
            event.preventDefault();
            setPwdVisible(!pwdVisible);
          }}
        >
          {pwdVisible ? (
            <ForwardedIconComponent
              name="Eye"
              className="relative top-[1px] h-5 w-5 text-placeholder-foreground hover:text-foreground"
            />
          ) : (
            <ForwardedIconComponent
              name="EyeOff"
              className="relative top-[1px] h-5 w-5 text-placeholder-foreground hover:text-foreground"
            />
          )}
        </button>
      )}
    </div>
  );
}
