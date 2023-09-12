import "ace-builds/src-noconflict/ace";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
// import "ace-builds/webpack-resolver";
import { useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { OUTPUT_DIALOG_SUBTITLE } from "../../constants/constants";
import { OutputModalType } from "../../types/components";
import BaseModal from "../baseModal";

export default function OutputModal({
  value,
  setValue,
  children,
}: OutputModalType): JSX.Element {
  const [open, setOpen] = useState(false);
  console.log(value);

  return (
    <BaseModal open={open} setOpen={setOpen} size={"small-h-full"}>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Header description={OUTPUT_DIALOG_SUBTITLE}>
        <span className="pr-2">Output Value</span>
        <IconComponent
          name="ArrowDownUp"
          className="h-6 w-6 pl-1 text-primary "
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col transition-all">
          <div className="h-full w-full"></div>

          <div className="flex h-fit w-full justify-end">
            <Button
              className="mt-3"
              type="submit"
              onClick={() => {
                setOpen(false);
              }}
            >
              Ok
            </Button>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
