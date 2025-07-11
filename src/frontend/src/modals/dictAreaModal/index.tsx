import useAlertStore from "@/stores/alertStore";
import { useEffect, useRef, useState } from "react";
import type { JsonEditor as VanillaJsonEditor } from "vanilla-jsoneditor";
import IconComponent from "../../components/common/genericIconComponent";
import JsonEditor from "../../components/core/jsonEditor";
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

  const setErrorData = useAlertStore((state) => state.setErrorData);
  ("");
  const jsonEditorRef = useRef<VanillaJsonEditor | null>(null);

  useEffect(() => {
    if (jsonEditorRef.current) {
      jsonEditorRef.current.set({ json: value || {} });
    }
  }, [value, open]);

  const handleSubmit = () => {
    if (onChange) {
      try {
        const componentValue = jsonEditorRef.current?.get() ?? { json: {} };
        const jsonValue =
          "json" in componentValue
            ? JSON.parse(JSON.stringify(componentValue.json))
            : JSON.parse(componentValue.text!);

        onChange(jsonValue);
        setOpen(false);
      } catch (error) {
        console.error("Error getting JSON:", error);
        setErrorData({
          title: "Error getting dictionary",
          list: ["Check your dictionary format"],
        });
      }
    }
  };

  const handleChangeType = (type: "array" | "object") => {
    jsonEditorRef?.current?.set(typeChanged(type));
  };

  const typeChanged = (type: "array" | "object") => {
    if (type === "array") {
      if (value && Object.keys(value).length > 0) {
        return { json: [value] };
      }
      return { json: [] };
    }
    if (value && Array.isArray(value) && value.length > 0) {
      return { json: value[0] };
    }
    return { json: {} };
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
    <BaseModal.Content overflowHidden>
      <div className="flex h-[500px] w-full flex-col transition-all">
        <JsonEditor
          data={{ json: value }}
          jsonRef={jsonEditorRef}
          readOnly={!onChange}
          height="500px"
          width="100%"
          className="h-full w-full overflow-auto"
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
      className="h-auto min-h-[500px] overflow-visible"
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
