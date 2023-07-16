import { useContext, useEffect } from "react";
import GenericModal from "../../modals/genericModal";
import { TextAreaComponentType } from "../../types/components";

import { ExternalLink } from "lucide-react";
import { TabsContext } from "../../contexts/tabsContext";

export default function TextAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: TextAreaComponentType) {
  const { setDisableCopyPaste } = useContext(TabsContext);

  useEffect(() => {
    if (disabled) {
      onChange("");
    }
  }, [disabled, onChange]);

  return (
    <div className={disabled ? "pointer-events-none w-full " : " w-full"}>
      <div className="flex w-full items-center">
        <input
          value={value}
          onFocus={() => {
            setDisableCopyPaste(true);
          }}
          onBlur={() => {
            setDisableCopyPaste(false);
          }}
          className={
            (editNode
              ? " input-edit-node "
              : " input-primary " + (disabled ? " input-disable" : "")) +
            " w-full"
          }
          placeholder={"Type something..."}
          onChange={(e) => {
            onChange(e.target.value);
          }}
        />
        <div>
          <GenericModal
            type={"text"}
            buttonText="Finishing Editing"
            modalTitle="Edit Text"
            value={value}
            setValue={(t: string) => {
              onChange(t);
            }}
          >
            {!editNode && (
              <ExternalLink
                strokeWidth={1.5}
                className={
                  "icons-parameters-comp" +
                  (disabled ? " text-ring" : " hover:text-accent-foreground")
                }
              />
            )}
          </GenericModal>
        </div>
      </div>
    </div>
  );
}
