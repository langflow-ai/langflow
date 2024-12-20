import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import JsonEditor from "../../components/core/jsonEditor";
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

  const handleChangeType = (type: "array" | "object") => {
    setComponentValue((value) => {
      if (type === "array") {
        if (value && Object.keys(value).length > 0) {
          return [value];
        }
        return [];
      }
      if (value && Array.isArray(value) && value.length > 0) {
        return value[0];
      }
      return {};
    });
  };

  const IteractiveReader = () => {
    return (
      <span>
        Customize your dictionary, adding or editing key-value pairs as needed.
        Supports adding new{" "}
        <span
          onClick={() => handleChangeType("object")}
          className="cursor-pointer underline"
        >
          objects &#123; &#125;
        </span>{" "}
        or{" "}
        <span
          onClick={() => handleChangeType("array")}
          className="cursor-pointer underline"
        >
          arrays [].
        </span>
      </span>
    );
  };

  const renderHeader = () => (
    <BaseModal.Header description={onChange ? IteractiveReader() : null}>
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
        <JsonEditor
          data={cloneDeep(componentValue)}
          onChange={onChange ? (data) => setComponentValue(data) : undefined}
          options={{
            mode: 'tree',
            modes: ['tree', 'code', 'form', 'text'],
            search: true,
            navigationBar: true,
            statusBar: true,
            mainMenuBar: true,
            readOnly: !onChange,
          }}
          height="400px"
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
