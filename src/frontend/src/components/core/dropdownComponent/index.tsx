import { PopoverAnchor } from "@radix-ui/react-popover";
import { useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import NodeDialog from "@/CustomNodes/GenericNode/components/NodeDialogComponent";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { BUILD_PANEL_COLLISION_PADDING_PX } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { getStatusColor } from "@/utils/stringManipulation";
import type { DropDownComponent } from "../../../types/components";
import { cn, filterNullOptions, formatName } from "../../../utils/utils";
import { default as ForwardedIconComponent } from "../../common/genericIconComponent";
import ShadTooltip from "../../common/shadTooltipComponent";
import { Button } from "../../ui/button";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "../../ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
} from "../../ui/popover";
import type { BaseInputProps } from "../parameterRenderComponent/types";
import { DropdownSearchInput } from "./components/DropdownSearchInput";
import { DropdownTrigger } from "./components/DropdownTrigger";
import {
  filterMetadataKeys,
  formatTooltipContent,
} from "./helpers/dropdown-search";
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

  const renderOptionsList = () => (
    <CommandList className="max-h-[300px] overflow-y-auto">
      <CommandGroup defaultChecked={false} className="p-0">
        {filteredOptions?.length > 0 ? (
          filteredOptions?.map((option, index) => (
            <ShadTooltip
              key={index}
              delayDuration={700}
              styleClasses="whitespace-pre-wrap"
              content={formatTooltipContent(
                option,
                index,
                filteredMetadata,
                firstWord,
              )}
            >
              <div>
                <CommandItem
                  value={option}
                  onSelect={(currentValue) => {
                    onSelect(
                      currentValue,
                      undefined,
                      undefined,
                      filteredMetadata?.[index],
                    );
                    setOpen(false);
                    setWaitingForResponse(false);
                  }}
                  className="w-full items-center rounded-none"
                  data-testid={`${option}-${index}-option`}
                >
                  <div
                    className="flex w-full items-center gap-2"
                    data-testid={`dropdown-option-${index}-container`}
                  >
                    {filteredMetadata?.[index]?.icon && (
                      <ForwardedIconComponent
                        name={filteredMetadata?.[index]?.icon || "Unknown"}
                        className="h-4 w-4 shrink-0 text-primary"
                      />
                    )}
                    <div
                      className={cn("flex w-full", {
                        "pl-2": !filteredMetadata?.[index]?.icon,
                      })}
                    >
                      <div className="text-[13px] mr-2 whitespace-nowrap flex-shrink-0">
                        {option}
                      </div>
                      {filteredMetadata?.[index]?.status && (
                        <span
                          className={`flex items-center pl-2 text-xs ${getStatusColor(
                            filteredMetadata?.[index]?.status,
                          )}`}
                        >
                          <LoadingTextComponent
                            text={filteredMetadata?.[
                              index
                            ]?.status?.toLowerCase()}
                          />
                        </span>
                      )}

                      {filteredMetadata && filteredMetadata?.length > 0 && (
                        <div className="ml-auto flex items-center overflow-hidden pl-2 text-muted-foreground">
                          {Object.entries(
                            filterMetadataKeys(filteredMetadata?.[index] || {}),
                          )
                            .filter(
                              ([key, value]) =>
                                value !== null && key !== "icon",
                            )
                            .map(([key, value], i, arr) => (
                              <div
                                key={key}
                                className={cn("flex items-center", {
                                  "flex-1 overflow-hidden":
                                    i === arr.length - 1,
                                })}
                              >
                                {i > 0 && (
                                  <ForwardedIconComponent
                                    name="Circle"
                                    className="mx-1 h-1 w-1 flex-shrink-0 overflow-visible fill-muted-foreground"
                                  />
                                )}
                                <div className="text-xs truncate">
                                  {`${String(value)} ${key}`}
                                </div>
                              </div>
                            ))}
                        </div>
                      )}
                      <div
                        className={cn("pl-2", {
                          "ml-auto":
                            !filteredMetadata || filteredMetadata.length === 0,
                        })}
                      >
                        <ForwardedIconComponent
                          name="Check"
                          className={cn(
                            "h-4 w-4 shrink-0 text-primary",
                            value === option ? "opacity-100" : "opacity-0",
                          )}
                        />
                      </div>
                    </div>
                  </div>
                </CommandItem>
              </div>
            </ShadTooltip>
          ))
        ) : (
          <CommandItem
            disabled
            className="w-full text-center text-sm text-muted-foreground px-2.5 py-1.5"
          >
            No options found
          </CommandItem>
        )}
      </CommandGroup>
      <CommandSeparator />
      {sourceOptions && sourceOptions?.fields && (
        <CommandGroup className="p-0">
          <CommandItem
            className="flex w-full cursor-pointer items-center justify-start gap-2 truncate rounded-none py-2.5 text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
            onSelect={(value) => {
              if (dialogInputs?.fields) {
                setOpenDialog(true);
              } else {
                handleSourceOptions(
                  sourceOptions?.fields?.data?.node?.name! || value,
                );
              }
            }}
          >
            <div className="flex items-center gap-2 pl-1 text-[13px] font-semibold">
              <ForwardedIconComponent name="Plus" className="h-3 w-3 " />
              {sourceOptions?.fields?.data?.node?.display_name}
            </div>
            {sourceOptions?.fields?.data?.node?.icon && (
              <div className="ml-auto">
                <ForwardedIconComponent
                  name={sourceOptions?.fields?.data?.node?.icon}
                  className="h-3 w-3 "
                />
              </div>
            )}
          </CommandItem>

          {hasRefreshButton && (
            <CommandItem
              className="flex w-full cursor-pointer items-center justify-start gap-2 truncate rounded-none py-2.5 text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
              onSelect={() => {
                handleRefreshButtonPress();
              }}
              data-testid={`refresh-dropdown-list-${name}`}
            >
              <div className="flex items-center gap-2 pl-1 text-[13px] font-semibold">
                <ForwardedIconComponent
                  name="RefreshCcw"
                  className={cn("h-3 w-3")}
                />
                Refresh list
              </div>
            </CommandItem>
          )}
          <NodeDialog
            open={openDialog}
            dialogInputs={dialogInputs}
            onClose={() => {
              setOpenDialog(false);
              setOpen(false);
            }}
            onCreated={(createdValue) => {
              setPendingSelect(createdValue);
            }}
            nodeId={nodeId!}
            name={name!}
            nodeClass={nodeClass!}
          />
        </CommandGroup>
      )}
    </CommandList>
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
        {renderOptionsList()}
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
