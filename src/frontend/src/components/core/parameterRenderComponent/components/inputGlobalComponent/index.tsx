import { useEffect } from "react";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import GeneralDeleteConfirmationModal from "@/shared/components/delete-confirmation-modal";
import { cn } from "../../../../../utils/utils";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import { CommandItem } from "../../../../ui/command";
import GlobalVariableModal from "../../../GlobalVariableModal/GlobalVariableModal";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputGlobalComponentType, InputProps } from "../../types";
import InputComponent from "../inputComponent";
import {
  useGlobalVariableValue,
  useInitialLoad,
  useUnavailableField,
} from "./hooks";
import type { GlobalVariable, GlobalVariableHandlers } from "./types";

export default function InputGlobalComponent({
  display_name,
  disabled,
  handleOnNewValue,
  value,
  id,
  load_from_db,
  password,
  allowCustomValue = true,
  editNode = false,
  placeholder,
  isToolMode = false,
  hasRefreshButton = false,
}: InputProps<string, InputGlobalComponentType>): JSX.Element {
  const { data: globalVariables } = useGetGlobalVariables();

  // // Safely cast the data to our typed interface
  const typedGlobalVariables: GlobalVariable[] = globalVariables ?? [];
  const currentValue = value ?? "";
  const isDisabled = disabled ?? false;
  const loadFromDb = load_from_db ?? false;

  // // Extract complex logic into custom hooks
  const valueExists = useGlobalVariableValue(
    currentValue,
    typedGlobalVariables,
  );
  const unavailableField = useUnavailableField(display_name, currentValue);

  useInitialLoad(
    isDisabled,
    loadFromDb,
    typedGlobalVariables,
    valueExists,
    unavailableField,
    handleOnNewValue,
  );

  // Clean up when selected variable no longer exists
  useEffect(() => {
    if (loadFromDb && currentValue && !valueExists && !isDisabled) {
      handleOnNewValue(
        { value: "", load_from_db: false },
        { skipSnapshot: true },
      );
    }
  }, [loadFromDb, currentValue, valueExists, isDisabled, handleOnNewValue]);

  // Create handlers object for better organization
  const handlers: GlobalVariableHandlers = {
    // Handler for deleting global variables
    handleVariableDelete: (variableName: string) => {
      if (value === variableName) {
        handleOnNewValue({
          value: "",
          load_from_db: false,
        });
      }
    },

    // Handler for selecting a global variable
    handleVariableSelect: (selectedValue: string) => {
      handleOnNewValue({
        value: selectedValue,
        load_from_db: selectedValue !== "",
      });
    },

    // Handler for input changes
    handleInputChange: (inputValue: string, skipSnapshot?: boolean) => {
      handleOnNewValue(
        { value: inputValue, load_from_db: false },
        { skipSnapshot },
      );
    },
  };

  // Render add new variable button
  const renderAddVariableButton = () => (
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
  );

  // Render delete button for each option
  const renderDeleteButton = (option: string) => (
    <GeneralDeleteConfirmationModal
      option={option}
      onConfirmDelete={() => handlers.handleVariableDelete(option)}
    />
  );

  // // Extract options list for better readability
  const variableOptions = typedGlobalVariables.map((variable) => variable.name);
  const selectedOption = loadFromDb && valueExists ? currentValue : "";

  return (
    <InputComponent
      nodeStyle
      popoverWidth="17.5rem"
      placeholder={getPlaceholder(disabled, placeholder)}
      id={id}
      editNode={editNode}
      disabled={disabled}
      password={password ?? false}
      value={currentValue}
      options={variableOptions}
      optionsPlaceholder="Global Variables"
      optionsIcon="Globe"
      optionsButton={renderAddVariableButton()}
      optionButton={renderDeleteButton}
      selectedOption={selectedOption}
      setSelectedOption={handlers.handleVariableSelect}
      onChange={handlers.handleInputChange}
      allowCustomValue={allowCustomValue}
      isToolMode={isToolMode}
      hasRefreshButton={hasRefreshButton}
    />
  );
}
