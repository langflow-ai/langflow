import { classNames } from "@/utils/utils";
import { useEffect, useState } from "react";
import { EDIT_TEXT_MODAL_TITLE } from "../../constants/constants";
import { TypeModal } from "../../constants/enums";
import GenericModal from "../../modals/genericModal";
import { Case } from "../../shared/components/caseComponent";
import { TextAreaComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

export default function TextAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  id = "",
  password,
  updateVisibility,
}: TextAreaComponentType): JSX.Element {
  // Clear text area
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("", undefined, true);
    }
  }, [disabled]);

  return (
    <div className={"flex w-full items-center" + (disabled ? "" : "")}>
      <div className="flex w-full items-center gap-3" data-testid={"div-" + id}>
        <Input
          id={id}
          data-testid={id}
          value={value}
          disabled={disabled}
          className={classNames(
            password !== undefined && password && value !== ""
              ? "text-clip password"
              : "",
            editNode ? "input-edit-node" : "",
            password && editNode ? "pr-8" : "",
            password && !editNode ? "pr-10" : "",
            "w-full",
          )}
          placeholder={"Type something..."}
          onChange={(event) => {
            onChange(event.target.value);
          }}
        />
        <GenericModal
          changeVisibility={updateVisibility}
          type={TypeModal.TEXT}
          buttonText="Finish Editing"
          modalTitle={EDIT_TEXT_MODAL_TITLE}
          value={value}
          setValue={(value: string) => {
            onChange(value);
          }}
          disabled={disabled}
          password={password}
        >
          <div
            className={
              "flex items-center" + (password ? "relative left-6" : "")
            }
          >
            <Button unstyled>
              <IconComponent
                strokeWidth={1.5}
                id={id}
                name="ExternalLink"
                className={
                  "icons-parameters-comp shrink-0" +
                  (disabled ? " text-ring" : " hover:text-accent-foreground")
                }
              />
            </Button>
          </div>
        </GenericModal>
        {password !== undefined && (
          <button
            type="button"
            tabIndex={-1}
            className={classNames(
              "mb-px",
              editNode
                ? "side-bar-button-size absolute bottom-[1.3rem] right-[4.2rem]"
                : "side-bar-button-size absolute bottom-4 right-[4.2rem]",
            )}
            onClick={(event) => {
              event.preventDefault();
              if (updateVisibility) updateVisibility();
            }}
          >
            {password ? (
              <IconComponent
              strokeWidth={1.5}
              id={id}
              name="Eye"
            />
            ) : (
              <IconComponent
              strokeWidth={1.5}
              id={id}
              name="EyeOff"
            />
            )}
          </button>
        )}
      </div>
    </div>
  );
}
