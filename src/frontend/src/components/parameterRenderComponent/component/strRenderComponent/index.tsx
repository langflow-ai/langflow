import Dropdown from "../../../dropdownComponent";
import InputGlobalComponent from "../../../inputGlobalComponent";
import InputListComponent from "../../../inputListComponent";
import { Multiselect } from "../../../multiselectComponent";
import TextAreaComponent from "../../../textAreaComponent";

export function StrRenderComponent({
  templateData,
  value,
  name,
  disabled,
  handleOnNewValue,
  editNode,
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
        value={!value || value === "" ? [""] : value}
        onChange={onChange}
      />
    ) : templateData.multiline ? (
      <TextAreaComponent
        id={"textarea-edit-" + templateData.name}
        data-testid={"textarea-edit-" + templateData.name}
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
      <Multiselect
        editNode={editNode}
        disabled={disabled}
        options={templateData.options || []}
        values={[value ?? "Choose an option"]}
        id={"multiselect-" + templateData.name}
        onValueChange={onChange}
      />
    );
  }

  if (!!templateData.options) {
    return (
      <Dropdown
        editNode={editNode}
        options={templateData.options}
        onSelect={onChange}
        value={value ?? "Choose an option"}
        id={"dropdown-edit-" + templateData.name}
      />
    );
  }
}
