import { PopoverAnchor } from "@radix-ui/react-popover";
import { useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { BUILD_PANEL_COLLISION_PADDING_PX } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import type { DropDownComponent } from "../../../types/components";
import { cn, filterNullOptions, formatName } from "../../../utils/utils";
import { default as ForwardedIconComponent } from "../../common/genericIconComponent";
import { Button } from "../../ui/button";
import { Command, CommandItem } from "../../ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
} from "../../ui/popover";
import type { BaseInputProps } from "../parameterRenderComponent/types";
import { DropdownOptionsList } from "./components/DropdownOptionsList";
import { DropdownSearchInput } from "./components/DropdownSearchInput";
import { DropdownTrigger } from "./components/DropdownTrigger";
import { useDropdownMutations } from "./hooks/useDropdownMutations";
import { useDropdownOptions } from "./hooks/useDropdownOptions";

export default function Dropdown({
  disabled,
  isLoading,
  value,
  options,
  optionsMetaData,
  combobox,
  onSelect,
  placeholder,
  editNode = false,
  id = "",
  children,
  nodeId,
  nodeClass,
  handleNodeClass,
  name,
  dialogInputs,
  externalOptions,
  handleOnNewValue,
  toggle,
  inspectionPanel,
  ...baseInputProps
}: BaseInputProps & DropDownComponent): JSX.Element {
  const { t } = useTranslation();
  const validOptions = useMemo(
    () => filterNullOptions(options),
    [options, value],
  );

  // Options / filtering state and its sync effects
  const {
    open,
    setOpen,
    openDialog,
    setOpenDialog,
    setWaitingForResponse,
    customValue,
    filteredOptions,
    setFilteredOptions,
    filteredMetadata,
    refreshOptions,
    setRefreshOptions,
    setPendingSelect,
    searchRoleByTerm,
  } = useDropdownOptions({
    value,
    options,
    validOptions,
    optionsMetaData,
    combobox,
    disabled,
    hasChildren: Boolean(children),
    onSelect,
  });
  const _nodes = useFlowStore((state) => state.nodes);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const buildInfo = useFlowStore((state) => state.buildInfo);
  const showingBuildPanel =
    isBuilding || !!buildInfo?.error || !!buildInfo?.success;

  const refButton = useRef<HTMLButtonElement>(null);

  // Initialize utilities and constants

  const sourceOptions = dialogInputs?.fields ? dialogInputs : externalOptions;
  const { firstWord } = formatName(name);
  const PopoverContentDropdown =
    children || editNode || inspectionPanel
      ? PopoverContent
      : PopoverContentWithoutPortal;
  const { helperText, hasRefreshButton } = baseInputProps;

  // Template mutation flows (create-from-source, refresh list)
  const { handleSourceOptions, handleRefreshButtonPress } =
    useDropdownMutations({
      value,
      name,
      nodeId,
      nodeClass,
      handleNodeClass,
      setOpen,
      setWaitingForResponse,
      setRefreshOptions,
    });

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      if (open && customValue) {
        const newOptions = [...validOptions];
        if (!newOptions.includes(customValue)) {
          newOptions.push(customValue);
        }

        setFilteredOptions(newOptions);

        handleOnNewValue?.({ value: customValue });
        onSelect(customValue);
        setOpen(false);
      }
    }
  };

  const renderLoadingButton = () => (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
    >
      <LoadingTextComponent text={t("dropdown.loadingOptions")} />
    </Button>
  );

  const renderPopoverContent = () => (
    <PopoverContentDropdown
      side="bottom"
      avoidCollisions
      collisionPadding={{
        bottom: showingBuildPanel ? BUILD_PANEL_COLLISION_PADDING_PX : 0,
      }}
      className="noflow nowheel nopan nodelete nodrag p-0"
      style={
        children ? {} : { minWidth: refButton?.current?.clientWidth ?? "200px" }
      }
    >
      <Command className="flex flex-col">
        {options?.length > 0 && (
          <DropdownSearchInput
            onSearch={searchRoleByTerm}
            onKeyDown={handleInputKeyDown}
          />
        )}
        <DropdownOptionsList
          filteredOptions={filteredOptions}
          filteredMetadata={filteredMetadata}
          firstWord={firstWord}
          value={value}
          onSelect={onSelect}
          setOpen={setOpen}
          setWaitingForResponse={setWaitingForResponse}
          sourceOptions={sourceOptions}
          dialogInputs={dialogInputs}
          handleSourceOptions={handleSourceOptions}
          hasRefreshButton={hasRefreshButton}
          handleRefreshButtonPress={handleRefreshButtonPress}
          name={name}
          openDialog={openDialog}
          setOpenDialog={setOpenDialog}
          setPendingSelect={setPendingSelect}
          nodeId={nodeId}
          nodeClass={nodeClass}
        />
        {!sourceOptions?.fields && hasRefreshButton && (
          <div className="border-t bg-background">
            <CommandItem className="flex cursor-pointer items-center justify-start gap-2 truncate rounded-b-md py-3 text-xs font-semibold text-muted-foreground">
              <Button
                className="w-full"
                unstyled
                data-testid={`refresh-dropdown-list-${name}`}
                onClick={() => {
                  handleRefreshButtonPress();
                }}
              >
                <div className="flex items-center gap-2 pl-1">
                  <ForwardedIconComponent
                    name="RefreshCcw"
                    className={cn("refresh-icon h-3 w-3 text-primary")}
                  />
                  Refresh list
                </div>
              </Button>
            </CommandItem>
          </div>
        )}
      </Command>
    </PopoverContentDropdown>
  );

  // Loading state
  if (Object.keys(validOptions).length === 0 && !combobox && isLoading) {
    return (
      <div>
        <span className="text-sm italic">{t("dropdown.loadingOptions")}</span>
      </div>
    );
  }

  // Main render
  return (
    <Popover open={open} onOpenChange={children ? () => {} : setOpen}>
      {children ? (
        <PopoverAnchor>{children}</PopoverAnchor>
      ) : refreshOptions || isLoading ? (
        renderLoadingButton()
      ) : validOptions.length === 1 &&
        toggle &&
        !combobox &&
        value === validOptions[0] ? (
        <div className="flex w-full items-center gap-2 truncate">
          {optionsMetaData?.[0]?.icon && (
            <ForwardedIconComponent
              name={optionsMetaData?.[0]?.icon}
              className="h-4 w-4 flex-shrink-0"
            />
          )}
          <span className="truncate text-sm">{value}</span>
        </div>
      ) : (
        <div className="w-full truncate">
          <DropdownTrigger
            disabled={disabled}
            validOptions={validOptions}
            combobox={combobox}
            sourceOptions={sourceOptions}
            hasRefreshButton={hasRefreshButton}
            editNode={editNode}
            open={open}
            refButton={refButton}
            id={id}
            value={value}
            options={options}
            placeholder={placeholder}
            helperText={helperText}
            filteredOptions={filteredOptions}
            filteredMetadata={filteredMetadata}
          />
        </div>
      )}
      {renderPopoverContent()}
    </Popover>
  );
}
