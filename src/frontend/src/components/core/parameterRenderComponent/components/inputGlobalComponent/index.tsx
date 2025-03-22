import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
} from "@/controllers/API/queries/variables";
import GeneralDeleteConfirmationModal from "@/shared/components/delete-confirmation-modal";
import GeneralGlobalVariableModal from "@/shared/components/global-variable-modal";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useEffect } from "react";
import DeleteConfirmationModal from "../../../../../modals/deleteConfirmationModal";
import useAlertStore from "../../../../../stores/alertStore";
import { cn } from "../../../../../utils/utils";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import { CommandItem } from "../../../../ui/command";
import GlobalVariableModal from "../../../GlobalVariableModal/GlobalVariableModal";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputGlobalComponentType, InputProps } from "../../types";
import InputComponent from "../inputComponent";

export default function InputGlobalComponent({
  display_name,
  disabled,
  handleOnNewValue,
  value,
  id,
  load_from_db,
  password,
  editNode = false,
  placeholder,
  isToolMode = false,
}: InputProps<string, InputGlobalComponentType>): JSX.Element {
  const { data: globalVariables } = useGetGlobalVariables();
  const unavailableFields = useGlobalVariablesStore(
    (state) => state.unavailableFields,
  );

  useEffect(() => {
    if (globalVariables && !disabled) {
      if (
        load_from_db &&
        !globalVariables.find((variable) => variable.name === value)
      ) {
        handleOnNewValue(
          { value: "", load_from_db: false },
          { skipSnapshot: true },
        );
      }
      if (
        !load_from_db &&
        value === "" &&
        unavailableFields &&
        Object.keys(unavailableFields).includes(display_name ?? "")
      ) {
        handleOnNewValue(
          { value: unavailableFields[display_name ?? ""], load_from_db: true },
          { skipSnapshot: true },
        );
      }
    }
  }, [globalVariables, unavailableFields, disabled]);

  function handleDelete(key: string) {
    if (value === key && load_from_db) {
      handleOnNewValue({ value: "", load_from_db: false });
    }
  }

  return (
    <InputComponent
      nodeStyle
      popoverWidth="17.5rem"
      placeholder={getPlaceholder(disabled, placeholder)}
      id={id}
      editNode={editNode}
      disabled={disabled}
      password={password ?? false}
      value={value ?? ""}
      options={globalVariables?.map((variable) => variable.name) ?? []}
      optionsPlaceholder={"Global Variables"}
      optionsIcon="Globe"
      optionsButton={
        <GlobalVariableModal referenceField={display_name} disabled={disabled}>
          <CommandItem value="doNotFilter-addNewVariable">
            <ForwardedIconComponent
              name="Plus"
              className={cn("mr-2 h-4 w-4 text-primary")}
              aria-hidden="true"
            />
            <span>Add New Variable</span>
          </CommandItem>
        </GlobalVariableModal>
      }
      optionButton={(option) => (
        <GeneralDeleteConfirmationModal
          option={option}
          onConfirmDelete={() => handleDelete(option)}
        />
      )}
      selectedOption={
        load_from_db &&
        globalVariables &&
        globalVariables?.map((variable) => variable.name).includes(value ?? "")
          ? value
          : ""
      }
      setSelectedOption={(value) => {
        handleOnNewValue({
          value: value,
          load_from_db: value !== "" ? true : false,
        });
      }}
      onChange={(value, skipSnapshot) => {
        handleOnNewValue(
          { value: value, load_from_db: false },
          { skipSnapshot },
        );
      }}
      isToolMode={isToolMode}
    />
  );
}
