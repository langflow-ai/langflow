import { useEffect } from "react";
import { useTranslation } from "react-i18next";
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

// Pydantic input classes that intrinsically represent secret fields. Only
// fields of these types should accept Credential-typed global variables. The
// dynamic `password` flag isn't sufficient on its own — components like
// TextInput's `use_global_variable` toggle flip `password=true` for display
// masking on a field whose intrinsic type (MultilineInput) is non-secret.
const SECRET_INPUT_TYPES = new Set(["SecretStrInput", "MultilineSecretInput"]);

export default function InputGlobalComponent({
  display_name,
  disabled,
  handleOnNewValue,
  value,
  id,
  load_from_db,
  password,
  _input_type,
  editNode = false,
  placeholder,
  isToolMode = false,
  hasRefreshButton = false,
  showParameter = true,
}: InputProps<string, InputGlobalComponentType> & {
  _input_type?: string;
}): JSX.Element | null {
  const { t } = useTranslation();
  const {
    data: globalVariables,
    isFetchedAfterMount: isGlobalVariablesFetchedAfterMount,
    isFetching: isGlobalVariablesFetching,
    isSuccess: isGlobalVariablesFetchSuccessful,
  } = useGetGlobalVariables();

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
  const canValidateMissingVariable =
    isGlobalVariablesFetchSuccessful &&
    !isGlobalVariablesFetching &&
    isGlobalVariablesFetchedAfterMount;

  useInitialLoad(
    isDisabled,
    loadFromDb,
    typedGlobalVariables,
    canValidateMissingVariable,
    valueExists,
    unavailableField,
    handleOnNewValue,
  );

  // Clean up when selected variable no longer exists.
  // Only validate against a successful, settled query result for this mount.
  // This avoids clearing values during the initial fetch, during background
  // refetches against cached data, or after failed requests.
  useEffect(() => {
    if (
      canValidateMissingVariable &&
      loadFromDb &&
      currentValue &&
      !valueExists &&
      !isDisabled
    ) {
      handleOnNewValue(
        { value: "", load_from_db: false },
        { skipSnapshot: true },
      );
    }
  }, [
    canValidateMissingVariable,
    loadFromDb,
    currentValue,
    valueExists,
    isDisabled,
    handleOnNewValue,
  ]);

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
        <span>{t("input.addNewVariable")}</span>
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

  let variableOptions = typedGlobalVariables.map((variable) => variable.name);

  if (
    loadFromDb &&
    currentValue &&
    !valueExists &&
    !variableOptions.includes(currentValue)
  ) {
    variableOptions = [...variableOptions, currentValue];
  }

  // Disable Credential-typed variables unless this is a true secret field
  // (SecretStrInput / MultilineSecretInput by intrinsic class). Falls back to
  // the dynamic `password` flag when the backend hasn't supplied `_input_type`.
  // Rule mirrors the backend validator's intent: credentials shouldn't flow
  // into fields whose values render in Message.text/status/traces.
  const isSecretField = _input_type
    ? SECRET_INPUT_TYPES.has(_input_type)
    : (password ?? false);
  const disabledOptions: Record<string, string> = isSecretField
    ? {}
    : Object.fromEntries(
        typedGlobalVariables
          .filter((v) => v.type === "Credential")
          .map((v) => [
            v.name,
            "Credential variables can only be used in secret fields (API keys, tokens). Select a Generic-typed variable, or change this variable's type to Generic if it isn't sensitive.",
          ]),
      );

  const selectedOption = loadFromDb ? currentValue : "";

  if (!showParameter) {
    return null;
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
      value={currentValue}
      options={variableOptions}
      disabledOptions={disabledOptions}
      optionsPlaceholder={t("globalVars.pageTitle")}
      optionsIcon="Globe"
      optionsButton={renderAddVariableButton()}
      optionButton={renderDeleteButton}
      selectedOption={selectedOption}
      setSelectedOption={handlers.handleVariableSelect}
      onChange={handlers.handleInputChange}
      isToolMode={isToolMode}
      hasRefreshButton={hasRefreshButton}
    />
  );
}
