import "ace-builds/src-noconflict/ace";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
// import "ace-builds/webpack-resolver";
import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import JsonView from "react18-json-view";
import "react18-json-view/src/dark.css";
import "react18-json-view/src/style.css";
import IconComponent from "../../components/common/genericIconComponent";
import { CODE_DICT_DIALOG_SUBTITLE } from "../../constants/constants";
import { useDarkStore } from "../../stores/darkStore";
import BaseModal from "../baseModal";

export default function DictAreaModal({
  children,
  onChange,
  value,
  disabled = false,
}: {
  children: JSX.Element;
  onChange?: (value: Object) => void;
  value: Object;
  disabled?: boolean;
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const isDark = useDarkStore((state) => state.dark);
  const [componentValue, setComponentValue] = useState(value);

  useEffect(() => {
    setComponentValue(value);
  }, [value, open]);

  const handleSubmit = () => {
    if (onChange) {
      onChange(componentValue);
      setOpen(false);
    }
  };

  const handleJsonChange = (edit) => {
    setComponentValue(edit.src);
  };

  const customizeCopy = (copy) => {
    navigator.clipboard.writeText(JSON.stringify(copy));
  };

  const renderHeader = () => (
    <BaseModal.Header description={onChange ? CODE_DICT_DIALOG_SUBTITLE : null}>
      <span className="pr-2">
        {onChange ? "Edit Dictionary" : "View Dictionary"}
      </span>
      <IconComponent
        name="BookMarked"
        className="h-6 w-6 pl-1 text-primary"
        aria-hidden="true"
      />
    </BaseModal.Header>
  );

  const renderContent = () => (
    <BaseModal.Content>
      <div className="flex h-full w-full flex-col transition-all">
        <JsonView
          theme="vscode"
          editable={!!onChange}
          enableClipboard
          onChange={handleJsonChange}
          src={cloneDeep(componentValue)}
          customizeCopy={customizeCopy}
        />
      </div>
    </BaseModal.Content>
  );

  return (
    <BaseModal
      size="medium-h-full"
      open={open}
      disable={disabled}
      setOpen={setOpen}
      onSubmit={onChange ? handleSubmit : undefined}
    >
      <BaseModal.Trigger className="h-full" asChild>
        {children}
      </BaseModal.Trigger>
      {renderHeader()}
      {renderContent()}
      <BaseModal.Footer submit={onChange ? { label: "Save" } : undefined} />
    </BaseModal>
  );
}
