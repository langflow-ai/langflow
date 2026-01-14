import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import { ReferenceInput } from "../../components/core/referenceInput";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import {
  EDIT_TEXT_PLACEHOLDER,
  TEXT_DIALOG_TITLE,
} from "../../constants/constants";
import type { textModalPropsType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";

export default function ComponentTextModal({
  value,
  setValue,
  children,
  disabled,
  readonly = false,
  password,
  changeVisibility,
  onCloseModal,
  nodeId,
}: textModalPropsType): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value);

  const textRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (typeof value === "string") setInputValue(value);
  }, [value, modalOpen]);

  useEffect(() => {
    if (!modalOpen) {
      onCloseModal?.();
    }
  }, [modalOpen]);

  const handleReferenceInputChange = (newValue: string) => {
    setInputValue(newValue);
  };

  const renderTextarea = (props?: {
    value: string;
    onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
    onKeyDown: (e: React.KeyboardEvent) => void;
    ref: React.RefObject<HTMLTextAreaElement>;
  }) => (
    <Textarea
      password={password}
      ref={props?.ref || textRef}
      className="form-input h-full w-full resize-none overflow-auto rounded-lg focus-visible:ring-1"
      value={props?.value ?? inputValue}
      onChange={
        props?.onChange ||
        ((event) => {
          setInputValue(event.target.value);
        })
      }
      placeholder={EDIT_TEXT_PLACEHOLDER}
      onKeyDown={
        props?.onKeyDown ||
        ((e) => {
          handleKeyDown(e, value, "");
        })
      }
      readOnly={readonly}
      id={"text-area-modal"}
      data-testid={"text-area-modal"}
    />
  );

  return (
    <BaseModal
      onChangeOpenModal={(open) => {}}
      open={modalOpen}
      setOpen={setModalOpen}
      size="x-large"
    >
      <BaseModal.Trigger disable={disabled} asChild>
        {children}
      </BaseModal.Trigger>
      <BaseModal.Header>
        <div className="flex w-full items-start gap-3">
          <div className="flex">
            <IconComponent
              name={"FileText"}
              className="h-6 w-6 pr-1 text-primary"
              aria-hidden="true"
            />
            <span className="pl-2" data-testid="modal-title">
              {TEXT_DIALOG_TITLE}
            </span>
          </div>
          {password !== undefined && (
            <div>
              <button
                onClick={() => {
                  if (changeVisibility) changeVisibility();
                }}
              >
                <IconComponent
                  name={password ? "Eye" : "EyeOff"}
                  className="h-6 w-6 cursor-pointer text-primary"
                />
              </button>
            </div>
          )}
        </div>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className={classNames("flex h-full w-full rounded-lg border")}>
          {nodeId ? (
            <ReferenceInput
              nodeId={nodeId}
              value={inputValue}
              onChange={handleReferenceInputChange}
              usePortal={true}
              className="h-full w-full"
            >
              {({ value: refValue, onChange, onKeyDown, ref }) =>
                renderTextarea({
                  value: refValue,
                  onChange: onChange as (
                    e: React.ChangeEvent<HTMLTextAreaElement>,
                  ) => void,
                  onKeyDown,
                  ref: ref as React.RefObject<HTMLTextAreaElement>,
                })
              }
            </ReferenceInput>
          ) : (
            renderTextarea()
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full shrink-0 items-end justify-end">
          <Button
            data-testid="genericModalBtnSave"
            id="genericModalBtnSave"
            disabled={readonly}
            onClick={() => {
              setValue(inputValue);
              setModalOpen(false);
            }}
            type="submit"
          >
            Finish Editing
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
