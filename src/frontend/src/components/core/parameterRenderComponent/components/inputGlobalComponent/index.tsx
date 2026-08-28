import { useTranslation } from "react-i18next";
import GlobalVariableDeleteConfirmation from "@/components/core/globalVariableDeleteConfirmation";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
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
  nodeId,
  load_from_db,
  password,
  _input_type,
  editNode = false,
  placeholder,
  isToolMode = false,
  hasRefreshButton = false,
  showParameter = true,
  ariaLabelledBy,
}: InputProps<string, InputGlobalComponentType> & {
  _input_type?: string;
}): JSX.Element | null {
  const { t } = useTranslation();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const providerScope = currentFlowId ? { flowId: currentFlowId } : undefined;
  const {
    data: globalVariables,
    isFetchedAfterMount: isGlobalVariablesFetchedAfterMount,
    isFetching: isGlobalVariablesFetching,
    fetchStatus: globalVariablesFetchStatus,
    isSuccess: isGlobalVariablesFetchSuccessful,
  } = useGetGlobalVariables({
    ...providerScope,
    enabled: Boolean(currentFlowId),
  });

  const currentValue = value ?? "";
  const isDisabled = disabled ?? false;
  const loadFromDb = load_from_db ?? false;
  const canUseScopedGlobalVariables =
    Boolean(currentFlowId) &&
    isGlobalVariablesFetchSuccessful &&
    !isGlobalVariablesFetching &&
    globalVariablesFetchStatus === "idle" &&
    globalVariables !== undefined;

  // Cached credentials are authorization-sensitive. Keep saved references in
  // the flow data, but do not surface them while the exact flow-scoped query is
  // fetching, paused, or failed. A successful result may come from another
  // observer of the same scoped cache entry after this component remounts.
  const typedGlobalVariables: GlobalVariable[] = canUseScopedGlobalVariables
    ? (globalVariables ?? [])
    : [];

  // // Extract complex logic into custom hooks
  const valueExists = useGlobalVariableValue(
    currentValue,
    typedGlobalVariables,
  );
  const unavailableField = useUnavailableField(
    display_name,
    currentValue,
    typedGlobalVariables,
  );
  // Clearing a saved reference is destructive, so require this observer's own
  // post-mount validation even when settled scoped data is safe to display.
  const canValidateMissingVariable =
    canUseScopedGlobalVariables && isGlobalVariablesFetchedAfterMount;

  useInitialLoad(
    isDisabled,
    loadFromDb,
    canValidateMissingVariable,
    valueExists,
    unavailableField,
    handleOnNewValue,
  );

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
      if (!canUseScopedGlobalVariables) return;
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
    <GlobalVariableModal
      referenceField={display_name}
      disabled={disabled}
      providerScope={providerScope}
    >
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
    <GlobalVariableDeleteConfirmation
      option={option}
      variableId={typedGlobalVariables.find((v) => v.name === option)?.id}
      onConfirmDelete={() => handlers.handleVariableDelete(option)}
      providerScope={providerScope}
    />
  );

  const variableOptions = typedGlobalVariables.map((variable) => variable.name);

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

  const selectedOption =
    loadFromDb && canUseScopedGlobalVariables && valueExists
      ? currentValue
      : "";
  const visibleValue = loadFromDb && !selectedOption ? "" : currentValue;

  if (!showParameter) {
    return null;
  }

  return (
    <InputComponent
      nodeStyle
      popoverWidth="17.5rem"
      placeholder={getPlaceholder(disabled, placeholder)}
      id={id}
      nodeId={nodeId}
      editNode={editNode}
      disabled={disabled}
      password={password ?? false}
      value={visibleValue}
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
      ariaLabelledBy={ariaLabelledBy}
    />
  );
}
