import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import GeneralDeleteConfirmationModal from "@/shared/components/delete-confirmation-modal";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useEffect, useMemo, useRef } from "react";

import { cn } from "../../../../../utils/utils";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import { CommandItem } from "../../../../ui/command";
import GlobalVariableModal from "../../../GlobalVariableModal/GlobalVariableModal";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputGlobalComponentType, InputProps } from "../../types";
import InputComponent from "../inputComponent";

export default function NewInputGlobalComponent({
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
  hasRefreshButton = false,
  ...baseInputProps
}: InputProps<string, InputGlobalComponentType>): JSX.Element {
  const { nodeInformationMetadata } = baseInputProps;

  const { data: globalVariables } = useGetGlobalVariables();
  const unavailableFields = useGlobalVariablesStore(
    (state) => state.unavailableFields,
  );

  const initialLoadCompleted = useRef(false);

  const valueExists = useMemo(() => {
    return (
      globalVariables?.some((variable) => variable.name === value) ?? false
    );
  }, [globalVariables, value]);

  const unavailableField = useMemo(() => {
    if (
      display_name &&
      unavailableFields &&
      Object.keys(unavailableFields).includes(display_name) &&
      value === ""
    ) {
      return unavailableFields[display_name];
    }
    return null;
  }, [unavailableFields, display_name]);

  useMemo(() => {
    if (disabled) {
      return;
    }

    if (load_from_db && globalVariables && !valueExists) {
      handleOnNewValue(
        { value: "", load_from_db: false },
        { skipSnapshot: true },
      );
    }
  }, [
    globalVariables,
    unavailableFields,
    disabled,
    load_from_db,
    valueExists,
    unavailableField,
    value,
    handleOnNewValue,
  ]);

  useEffect(() => {
    if (initialLoadCompleted.current || disabled || unavailableField === null) {
      return;
    }

    handleOnNewValue(
      { value: unavailableField, load_from_db: true },
      { skipSnapshot: true },
    );

    initialLoadCompleted.current = true;
  }, [unavailableField, disabled, load_from_db, value, handleOnNewValue]);

  function handleDelete(key: string) {
    if (value === key) {
      handleOnNewValue({ value: "", load_from_db: load_from_db });
    }
  }

  return (
    <InputComponent
      nodeStyle
      popoverWidth="17.5rem"
      placeholder="sk-..."
      id={id}
      editNode={editNode}
      disabled={disabled}
      name={nodeInformationMetadata?.variableName}
      password={true} // Shows eye icon
      value={value ?? ""}
      options={globalVariables?.map((variable) => variable.name) ?? []}
      optionsIcon="Globe"
      selectedOption={load_from_db && valueExists ? value : ""}
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
