import { useEffect, useRef, useState } from "react";
import { Textarea } from "../../components/ui/textarea";
import {
  EDIT_TEXT_PLACEHOLDER,
  TEXT_DIALOG_TITLE,
} from "../../constants/constants";
import { queryModalPropsType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";

export default function QueryModal({
  value,
  setValue,
  title,
  description,
  placeholder,
  children,
  disabled,
}: queryModalPropsType): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value);

  const textRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (typeof value === "string") setInputValue(value);
  }, [value, modalOpen]);

  return (
    <BaseModal
      onChangeOpenModal={(open) => {}}
      open={modalOpen}
      setOpen={setModalOpen}
      size="small-query"
    >
      <BaseModal.Trigger disable={disabled} asChild>
        {children}
      </BaseModal.Trigger>
      <BaseModal.Header>
        <div className="flex w-full items-start gap-3">
          <div className="flex">
            <span data-testid="modal-title">{title ?? TEXT_DIALOG_TITLE}</span>
          </div>
        </div>
      </BaseModal.Header>
      <BaseModal.Content className="flex flex-col gap-2" overflowHidden>
        <div className={classNames("flex h-full w-full rounded-lg border")}>
          <Textarea
            ref={textRef}
            className="form-input h-full min-h-28 w-full overflow-auto rounded-lg focus-visible:ring-1"
            value={inputValue}
            onChange={(event) => {
              setInputValue(event.target.value);
            }}
            placeholder={placeholder ?? EDIT_TEXT_PLACEHOLDER}
            onKeyDown={(e) => {
              handleKeyDown(e, value, "");
            }}
            id={"text-area-modal"}
            data-testid={"text-area-modal"}
          />
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-muted-foreground text-sm">{description}</p>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Apply",
          dataTestId: "genericModalBtnSave",
          onClick: () => {
            setValue(inputValue);
            setModalOpen(false);
          },
        }}
      />
    </BaseModal>
  );
}
