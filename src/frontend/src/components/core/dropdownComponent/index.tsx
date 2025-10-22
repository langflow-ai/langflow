import { PopoverAnchor } from "@radix-ui/react-popover";
import Fuse from "fuse.js";
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import NodeDialog from "@/CustomNodes/GenericNode/components/NodeDialogComponent";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { RECEIVING_INPUT_VALUE, SELECT_AN_OPTION } from "@/constants/constants";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import {
  convertStringToHTML,
  getStatusColor,
} from "@/utils/stringManipulation";
import type { DropDownComponent } from "../../../types/components";
import {
  cn,
  filterNullOptions,
  formatName,
  groupByFamily,
} from "../../../utils/utils";
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
  PopoverTrigger,
} from "../../ui/popover";
import type { BaseInputProps } from "../parameterRenderComponent/types";

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
  ...baseInputProps
}: BaseInputProps & DropDownComponent): JSX.Element {
  const validOptions = useMemo(
    () => filterNullOptions(options),
    [options, value],
  );

  // Initialize state and refs
  const [open, setOpen] = useState(children ? true : false);
  const [openDialog, setOpenDialog] = useState(false);
  const [waitingForResponse, setWaitingForResponse] = useState(false);
  const [customValue, setCustomValue] = useState("");
  const nodes = useFlowStore((state) => state.nodes);

  const [filteredOptions, setFilteredOptions] = useState(() => {
    // Include the current value in filteredOptions if it's a custom value not in validOptions
    if (value && !validOptions.includes(value) && combobox) {
      return [...validOptions, value];
    }
    return validOptions;
  });
  const [filteredMetadata, setFilteredMetadata] = useState(optionsMetaData);
  const [refreshOptions, setRefreshOptions] = useState(false);
  const refButton = useRef<HTMLButtonElement>(null);

  value = useMemo(() => {
    // We should only reset the value if it's not in options and not in filteredOptions
    // and not a recently added custom value
    if (!options.includes(value) && !filteredOptions.includes(value)) {
      if (value) onSelect("", undefined, true);
      return null;
    }
    return value;
  }, [value, options, filteredOptions]);

  // Initialize utilities and constants

  const sourceOptions = dialogInputs?.fields ? dialogInputs : externalOptions;
  const { firstWord } = formatName(name);
  const fuse = new Fuse(validOptions, { keys: ["name", "value"] });
  const PopoverContentDropdown =
    children || editNode ? PopoverContent : PopoverContentWithoutPortal;
  const { helperText, hasRefreshButton } = baseInputProps;

  // API and store hooks
  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
  });
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Utility functions
  const filterMetadataKeys = (
    metadata: Record<string, any> = {},
    excludeKeys: string[] = ["api_endpoint", "icon", "status", "org_id"],
  ) => {
    return Object.fromEntries(
      Object.entries(metadata).filter(([key]) => !excludeKeys.includes(key)),
    );
  };

  const searchRoleByTerm = async (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setCustomValue(value);

    if (!value) {
      // If search is cleared, show all options
      // Preserve any custom values that were in filteredOptions
      const customValuesInFiltered = filteredOptions.filter(
        (option) => !validOptions.includes(option) && option === customValue,
      );
      setFilteredOptions([...validOptions, ...customValuesInFiltered]);
      setFilteredMetadata(optionsMetaData);
      return;
    }

    // Search existing options
    const searchValues = fuse.search(value);
    let filtered = searchValues.map((search) => search.item);

    // If the search value exactly matches one of the custom options, include it
    const customOptions = filteredOptions.filter(
      (option) => !validOptions.includes(option),
    );
    const matchingCustomOption = customOptions.find(
      (option) => option.toLowerCase() === value.toLowerCase(),
    );

    // Include matching custom options or allow adding the current search if combobox is true
    if (matchingCustomOption && !filtered.includes(matchingCustomOption)) {
      filtered.push(matchingCustomOption);
    } else if (
      combobox &&
      value &&
      !filtered.some((opt) => opt.toLowerCase() === value.toLowerCase())
    ) {
      // If combobox is enabled and we're typing a new value, include it in the filtered list
      filtered = [value, ...filtered];
    }

    // Update filteredOptions with the search results
    setFilteredOptions(filtered);

    // Create a new metadata array that directly maps to filtered options
    if (optionsMetaData) {
      // Create a map of option -> metadata for quick lookup
      const metadataMap: Record<string, any> = {};
      validOptions.forEach((option, index) => {
        if (optionsMetaData[index]) {
          metadataMap[option] = optionsMetaData[index];
        }
      });

      // Map each filtered option to its metadata (or undefined for custom values)
      const newMetadata = filtered.map((option) => metadataMap[option]);
      setFilteredMetadata(newMetadata);
    } else {
      setFilteredMetadata(undefined);
    }
  };

  const handleSourceOptions = async (value: string) => {
    setWaitingForResponse(true);
    setOpen(false);

    await mutateTemplate(
      value,
      nodeId,
      nodeClass!,
      handleNodeClass,
      postTemplateValue,
      setErrorData,
      name,
    );

    // TODO: this is a hack to make the connect other models option work
    // we should find a better way to do this
    try {
      if (value === "connect_other_models") {
        const store = useFlowStore.getState();
        const node = store.getNode(nodeId!);
        const templateField = node?.data?.node?.template?.[name!];
        if (!templateField) return;

        const inputTypes: string[] =
          (Array.isArray(templateField.input_types)
            ? templateField.input_types
            : []) || [];
        const effectiveInputTypes =
          inputTypes.length > 0 ? inputTypes : ["LanguageModel"];
        const tooltipTitle: string =
          (inputTypes && inputTypes.length > 0
            ? inputTypes.join("\n")
            : templateField.type) || "";

        const myId = scapedJSONStringfy({
          inputTypes: effectiveInputTypes,
          type: templateField.type,
          id: nodeId,
          fieldName: name,
          proxy: templateField.proxy,
        });

        const typesData = useTypesStore.getState().data;
        const grouped = groupByFamily(
          typesData,
          (effectiveInputTypes && effectiveInputTypes.length > 0
            ? effectiveInputTypes.join("\n")
            : tooltipTitle) || "",
          true,
          store.nodes,
        );

        // Build a pseudo source so compatible target handles (left side) glow
        const pseudoSourceHandle = scapedJSONStringfy({
          fieldName: name,
          id: nodeId,
          inputTypes: effectiveInputTypes,
          type: "str",
        });

        const filterObj = {
          source: undefined,
          sourceHandle: undefined,
          target: nodeId,
          targetHandle: pseudoSourceHandle,
          type: "LanguageModel",
          // Use a generic color; exact tone is resolved when user hovers/clicks handles
          color: "datatype-fuchsia",
        } as any;

        // Show compatible handles glow
        store.setFilterEdge(grouped);
        store.setFilterType(filterObj);
      }
    } finally {
      setWaitingForResponse(false);
    }
  };

  const handleRefreshButtonPress = async () => {
    setRefreshOptions(true);
    setOpen(false);

    await mutateTemplate(
      value,
      nodeId,
      nodeClass!,
      handleNodeClass,
      postTemplateValue,
      setErrorData,
    )?.then(() => {
      setTimeout(() => {
        setRefreshOptions(false);
      }, 2000);
    });
  };

  const formatTooltipContent = (option: string, index: number) => {
    if (!filteredMetadata?.[index]) return option;

    const metadata = filteredMetadata[index];
    const metadataEntries = Object.entries(metadata)
      .filter(([key, value]) => value !== null && key !== "icon")
      .map(([key, value]) => {
        const displayValue =
          typeof value === "string" && value.length > 20
            ? `${value.substring(0, 30)}...`
            : String(value);
        return `${key}: ${displayValue}`;
      });

    return metadataEntries.length > 0
      ? `${firstWord}: ${option}\n${metadataEntries.join("\n")}`
      : option;
  };

  // Effects
  useEffect(() => {
    if (disabled && value !== "") {
      onSelect("", undefined, true);
    }
  }, [disabled]);

  useEffect(() => {
    if (open) {
      // Check if filteredOptions contains any custom values not in validOptions
      const customValuesInFiltered = filteredOptions.filter(
        (option) => !validOptions.includes(option) && option === customValue,
      );

      // If there are custom values, preserve them when resetting filtered options
      if (customValuesInFiltered.length > 0 && combobox) {
        setFilteredOptions([...validOptions, ...customValuesInFiltered]);

        // Reset filteredMetadata to match the new filteredOptions
        if (optionsMetaData) {
          const metadataMap: Record<string, any> = {};
          validOptions.forEach((option, index) => {
            if (optionsMetaData[index]) {
              metadataMap[option] = optionsMetaData[index];
            }
          });

          const newMetadata = [...validOptions, ...customValuesInFiltered].map(
            (option) => metadataMap[option],
          );
          setFilteredMetadata(newMetadata);
        }
      } else {
        setFilteredOptions(validOptions);
        setFilteredMetadata(optionsMetaData);
      }
    }
    if (!combobox && value && !validOptions.includes(value)) {
      onSelect("", undefined, true);
    }
  }, [open, validOptions]);

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
      <LoadingTextComponent text="Loading options" />
    </Button>
  );

  const renderSelectedIcon = () => {
    const selectedIndex = filteredOptions.findIndex(
      (option) => option === value,
    );
    const iconMetadata =
      selectedIndex >= 0 ? filteredMetadata?.[selectedIndex]?.icon : undefined;

    return iconMetadata ? (
      <ForwardedIconComponent
        name={iconMetadata}
        className="h-4 w-4 flex-shrink-0"
      />
    ) : null;
  };

  const renderTriggerButton = () => (
    <div className="flex w-full flex-col">
      <PopoverTrigger asChild>
        <Button
          disabled={
            disabled ||
            (Object.keys(validOptions).length === 0 &&
              !combobox &&
              !sourceOptions?.fields?.data?.node?.template &&
              !hasRefreshButton &&
              !sourceOptions?.fields)
          }
          variant="primary"
          size="xs"
          role="combobox"
          ref={refButton}
          aria-expanded={open}
          data-testid={id}
          className={cn(
            editNode
              ? "dropdown-component-outline input-edit-node"
              : "dropdown-component-false-outline py-2",
            "no-focus-visible w-full justify-between font-normal disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          <span
            className="flex w-full items-center gap-2 overflow-hidden"
            data-testid={`value-dropdown-${id}`}
          >
            {value && <>{renderSelectedIcon()}</>}
            <span className="truncate">
              {disabled ? (
                RECEIVING_INPUT_VALUE
              ) : (
                <>
                  {
                    options?.includes(value) ? (
                      value
                    ) : // this logic is used for the agents component, if you update make sure to test the agent component
                    sourceOptions?.fields?.data?.node?.name ===
                      "connect_other_models" ? (
                      <span className="text-muted-foreground">
                        <LoadingTextComponent
                          text={placeholder || SELECT_AN_OPTION}
                        />
                      </span>
                    ) : (
                      placeholder || SELECT_AN_OPTION
                    )
                    // ) : (
                    //   <span className="text-muted-foreground">
                    //     <LoadingTextComponent
                    //       text={placeholder || SELECT_AN_OPTION}
                    //     />
                    //   </span>
                    // )}
                  }
                </>
              )}
            </span>
          </span>

          <ForwardedIconComponent
            name={disabled ? "Lock" : "ChevronsUpDown"}
            className={cn(
              "ml-2 h-4 w-4 shrink-0 text-foreground",
              disabled
                ? "text-placeholder-foreground hover:text-placeholder-foreground"
                : "hover:text-foreground",
            )}
          />
        </Button>
      </PopoverTrigger>
      {helperText && (
        <span className="pt-2 text-xs text-muted-foreground">
          {convertStringToHTML(helperText)}
        </span>
      )}
    </div>
  );

  const renderSearchInput = () => (
    <div className="flex items-center border-b px-2.5">
      <ForwardedIconComponent
        name="search"
        className="mr-2 h-4 w-4 shrink-0 opacity-50"
      />
      <input
        onChange={searchRoleByTerm}
        onKeyDown={handleInputKeyDown}
        placeholder="Search options..."
        className="flex h-9 w-full rounded-md bg-transparent py-3 text-[13px] outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
        autoComplete="off"
        data-testid="dropdown_search_input"
      />
    </div>
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
              content={formatTooltipContent(option, index)}
            >
              <div>
                <CommandItem
                  value={option}
                  onSelect={(currentValue) => {
                    onSelect(currentValue);
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
      avoidCollisions={!!children}
      className="noflow nowheel nopan nodelete nodrag p-0"
      style={
        children ? {} : { minWidth: refButton?.current?.clientWidth ?? "200px" }
      }
    >
      <Command className="flex flex-col">
        {options?.length > 0 && renderSearchInput()}
        {renderOptionsList()}
        {!sourceOptions?.fields && hasRefreshButton && (
          <div className="sticky bottom-0 border-t bg-background">
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
        <span className="text-sm italic">Loading...</span>
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
        <div className="w-full truncate">{renderTriggerButton()}</div>
      )}
      {renderPopoverContent()}
    </Popover>
  );
}
