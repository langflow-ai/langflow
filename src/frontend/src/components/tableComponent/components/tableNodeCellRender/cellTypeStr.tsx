import Dropdown from "../../../dropdownComponent";
import InputGlobalComponent from "../../../inputGlobalComponent";
import InputListComponent from "../../../inputListComponent";
import { Multiselect } from "../../../multiselectComponent";
import TextAreaComponent from "../../../textAreaComponent";

export function renderStrType({
  templateData,
  templateValue,
  disabled,
  handleOnNewValue,
}) {
  if (!templateData.options) {
    return templateData?.list ? (
      <InputListComponent
        componentName={templateData.key ?? undefined}
        editNode={true}
        disabled={disabled}
        value={!templateValue || templateValue === "" ? [""] : templateValue}
        onChange={(value: string[]) => {
          handleOnNewValue(value, templateData.key);
        }}
      />
    ) : templateData.multiline ? (
      <TextAreaComponent
        id={"textarea-edit-" + templateData.name}
        data-testid={"textarea-edit-" + templateData.name}
        disabled={disabled}
        editNode={true}
        value={templateValue ?? ""}
        onChange={(value: string | string[]) => {
          handleOnNewValue(value, templateData.key);
        }}
      />
    ) : (
      <InputGlobalComponent
        disabled={disabled}
        editNode={true}
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
        editNode={true}
        disabled={disabled}
        options={templateData.options || []}
        value={templateValue ?? "Choose an option"}
        id={"multiselect-" + templateData.name}
        onValueChange={(value) => handleOnNewValue(value, templateData.key)}
      />
    );
  }

  if (!!templateData.options) {
    return (
      <Dropdown
        editNode={true}
        options={templateData.options}
        onSelect={(value) => handleOnNewValue(value, templateData.key)}
        value={templateValue ?? "Choose an option"}
        id={"dropdown-edit-" + templateData.name}
      />
    );
  }
}
