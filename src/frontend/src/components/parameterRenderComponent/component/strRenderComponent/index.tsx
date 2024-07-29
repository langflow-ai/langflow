import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { InputFieldType } from "@/types/api";
import Dropdown from "../../../dropdownComponent";
import InputGlobalComponent from "../../../inputGlobalComponent";
import InputListComponent from "../../../inputListComponent";
import MultiselectComponent from "../../../multiselectComponent";
import TextAreaComponent from "../../../textAreaComponent";

export function StrRenderComponent({
  templateData,
  value,
  name,
  disabled,
  handleOnNewValue,
  editNode,
  id,
}: {
  templateData: Partial<InputFieldType>;
  value: any;
  name: string;
  disabled: boolean;
  handleOnNewValue: handleOnNewValueType;
  editNode: boolean;
  id: string;
}) {
  const onChange = (value: any, dbValue?: boolean, skipSnapshot?: boolean) => {
    handleOnNewValue({ value, load_from_db: dbValue }, { skipSnapshot });
  };

  if (!templateData.options) {
    return templateData?.list ? (
      <InputListComponent
        componentName={name ?? undefined}
        editNode={editNode}
        disabled={disabled}
        value={value || [""]}
        onChange={onChange}
        id={`inputlist_${id}`}
      />
    ) : templateData.multiline ? (
      <TextAreaComponent
        password={templateData.password}
        updateVisibility={() => {
          if (templateData.password !== undefined) {
            handleOnNewValue(
              { password: !templateData.password },
              { skipSnapshot: true },
            );
          }
        }}
        id={`textarea_${id}`}
        disabled={disabled}
        editNode={editNode}
        value={value ?? ""}
        onChange={onChange}
      />
    ) : (
      <InputGlobalComponent
        disabled={disabled}
        editNode={editNode}
        onChange={onChange}
        name={name}
        data={templateData}
      />
    );
  }

  if (!!templateData.options && !!templateData?.list) {
    return (
      <MultiselectComponent
        editNode={editNode}
        disabled={disabled}
        options={
          (Array.isArray(templateData.options)
            ? templateData.options
            : [templateData.options]) || []
        }
        combobox={templateData.combobox}
        value={
          (Array.isArray(templateData.value)
            ? templateData.value
            : [templateData.value]) || []
        }
        id={`multiselect_${id}`}
        onSelect={onChange}
      />
    );
  }

  if (!!templateData.options) {
    return (
      <Dropdown
        editNode={editNode}
        options={templateData.options}
        onSelect={onChange}
        combobox={templateData.combobox}
        value={value || ""}
        id={`dropdown_${id}`}
      />
    );
  }
}
