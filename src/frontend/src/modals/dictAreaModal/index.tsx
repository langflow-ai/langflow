import "ace-builds/src-noconflict/ace";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
// import "ace-builds/webpack-resolver";
import { useState } from "react";
import JsonView from "react18-json-view";
import "react18-json-view/src/dark.css";
import "react18-json-view/src/style.css";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { CODE_DICT_DIALOG_SUBTITLE } from "../../constants/constants";
import BaseModal from "../baseModal";

export default function DictAreaModal({
  children,
  onChange,
  value,
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const [dictObj, setDictObj] = useState(value);

  return (
    <BaseModal size="medium" open={open} setOpen={setOpen}>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Header description={CODE_DICT_DIALOG_SUBTITLE}>
        <span className="pr-2">Edit Dictionary</span>
        <IconComponent
          name="BookMarked"
          className="h-6 w-6 pl-1 text-primary "
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col transition-all">
          <JsonView
            theme="vscode"
            dark={true}
            editable
            enableClipboard
            onEdit={(edit) => {
              setDictObj(edit["src"]);
            }}
            src={dictObj}
          />
          <div className="flex h-fit w-full justify-end">
            <Button
              className="mt-3"
              type="submit"
              onClick={() => {
                onChange(dictObj);
                setOpen(false);
              }}
            >
              Save
            </Button>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
