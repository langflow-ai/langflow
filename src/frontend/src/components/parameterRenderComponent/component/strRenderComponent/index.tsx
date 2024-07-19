import Dropdown from "../../../dropdownComponent";
import InputGlobalComponent from "../../../inputGlobalComponent";
import InputListComponent from "../../../inputListComponent";
import { Multiselect } from "../../../multiselectComponent";
import TextAreaComponent from "../../../textAreaComponent";

export function StrRenderComponent({
  templateData,
  value,
  disabled,
  handleOnNewValue,
  editNode,
}) {
  if (!templateData.options) {
    return templateData?.list ? (
      <InputListComponent
        componentName={templateData.key ?? undefined}
        editNode={editNode}
        disabled={disabled}
        value={!value || value === "" ? [""] : value}
        onChange={(value: string[]) => {
          handleOnNewValue(value, templateData.key);
        }}
      />
    ) : templateData.multiline ? (
      <TextAreaComponent
        id={"textarea-edit-" + templateData.name}
        data-testid={"textarea-edit-" + templateData.name}
        disabled={disabled}
        editNode={editNode}
        value={value ?? ""}
        onChange={(value: string | string[]) => {
          handleOnNewValue(value, templateData.key);
        }}
      />
    ) : (
      <InputGlobalComponent
        disabled={disabled}
        editNode={editNode}
        onChange={(value, dbValue, snapshot) =>
          handleOnNewValue(value, templateData.key, dbValue)
        }
        name={templateData.key}
        data={templateData}
      />
    );
  }

  if (!!templateData.options && !!templateData?.list) {
    return (
      <Multiselect
        editNode={editNode}
        disabled={disabled}
        options={templateData.options || []}
        values={[value ?? "Choose an option"]}
        id={"multiselect-" + templateData.name}
        onValueChange={(value) => handleOnNewValue(value, templateData.key)}
      />
    );
  }

  if (!!templateData.options) {
    return (
      <Dropdown
        editNode={editNode}
        options={templateData.options}
        onSelect={(value) => handleOnNewValue(value, templateData.key)}
        value={value ?? "Choose an option"}
        id={"dropdown-edit-" + templateData.name}
      />
    );
  }
}
