import { useContext, useEffect, useState } from "react";
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
  const [myValue, setMyValue] = useState(value);
  const { setDisableCopyPaste } = useContext(TabsContext);

  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);

  return (
    <div className={disabled ? "pointer-events-none w-full " : " w-full"}>
      <div className="flex w-full items-center">
        <input
          value={myValue}
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
            setMyValue(e.target.value);
            onChange(e.target.value);
          }}
        />
        <div>
          <GenericModal
            type={"text"}
            buttonText="Finishing Editing"
            modalTitle="Edit Text"
            value={myValue}
            setValue={(t: string) => {
              setMyValue(t);
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
