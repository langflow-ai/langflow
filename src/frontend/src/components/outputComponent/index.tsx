import { useEffect } from "react";
import { OutputComponentType } from "../../types/components";

import OutputModal from "../../modals/outputModal";
import { classNames } from "../../utils/utils";
import { Input } from "../ui/input";

export default function OutputComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: OutputComponentType): JSX.Element {
  useEffect(() => {
    if (disabled) {
      onChange([""]);
    }
  }, [disabled]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex w-full gap-3">
        {value && value.valid ? (
          <OutputModal value={value} setValue={(value: string) => {}}>
            <Input
              disabled={true}
              type="text"
              value={value?.params ? value.params : "Build flow to output"}
              className={classNames(
                editNode ? "input-edit-node" : "",
                value?.params ? "cursor-pointer" : "cursor-default"
              )}
              placeholder="Type something..."
              onChange={(event) => {}}
              onKeyDown={(e) => {
                if (e.ctrlKey && e.key === "Backspace") {
                  e.preventDefault();
                  e.stopPropagation();
                }
              }}
            />
          </OutputModal>
        ) : (
          <Input
            disabled={true}
            type="text"
            value={"Build flow to output"}
            className={classNames(
              editNode ? "input-edit-node cursor-default" : "cursor-default"
            )}
            placeholder="Type something..."
            onChange={(event) => {}}
            onKeyDown={(e) => {
              if (e.ctrlKey && e.key === "Backspace") {
                e.preventDefault();
                e.stopPropagation();
              }
            }}
          />
        )}
      </div>
    </div>
  );
}
