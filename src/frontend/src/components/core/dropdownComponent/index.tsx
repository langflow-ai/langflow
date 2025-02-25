import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import NodeDialog from "@/CustomNodes/GenericNode/components/NodeDialogComponent";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useAlertStore from "@/stores/alertStore";
import { getStatusColor } from "@/utils/stringManipulation";
import { PopoverAnchor } from "@radix-ui/react-popover";
import Fuse from "fuse.js";
import { cloneDeep } from "lodash";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { DropDownComponent } from "../../../types/components";
import {
  cn,
  filterNullOptions,
  formatName,
  formatPlaceholderName,
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
import { BaseInputProps } from "../parameterRenderComponent/types";

export default function Dropdown({
  disabled,
  isLoading,
  value,
  options,
  optionsMetaData,
  combobox,
  onSelect,
  editNode = false,
  id = "",
  children,
  name,
  dialogInputs,
  ...baseInputProps
}: BaseInputProps & DropDownComponent): JSX.Element {
  const validOptions = useMemo(() => filterNullOptions(options), [options]);

  // Initialize state and refs
  const [open, setOpen] = useState(children ? true : false);
  const [openDialog, setOpenDialog] = useState(false);
  const [customValue, setCustomValue] = useState("");
  const [filteredOptions, setFilteredOptions] = useState(validOptions);
  const [refreshOptions, setRefreshOptions] = useState(false);
  const refButton = useRef<HTMLButtonElement>(null);

  // Initialize utilities and constants
  const placeholderName = name
    ? formatPlaceholderName(name)
    : "Choose an option...";
  const { firstWord } = formatName(name);
  const fuse = new Fuse(validOptions, { keys: ["name", "value"] });
  const PopoverContentDropdown =
    children || editNode ? PopoverContent : PopoverContentWithoutPortal;
  const { nodeClass, nodeId, handleNodeClass, tooltip } = baseInputProps;

  // API and store hooks
  const postTemplateValue = usePostTemplateValue({
    parameterId: name || "",
    nodeId: nodeId || "",
    node: nodeClass!,
  });
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Utility functions
  const filterMetadataKeys = (
    metadata: Record<string, any> = {},
    excludeKeys: string[] = ["api_endpoint", "icon", "status"],
  ) => {
    return Object.fromEntries(
      Object.entries(metadata).filter(([key]) => !excludeKeys.includes(key)),
    );
  };

  const searchRoleByTerm = async (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    const searchValues = fuse.search(value);
    const filtered = searchValues.map((search) => search.item);
    if (!filtered.includes(value) && combobox && value) filtered.push(value);
    setFilteredOptions(value ? filtered : validOptions);
    setCustomValue(value);
  };

  const handleRefreshButtonPress = async () => {
    setRefreshOptions(true);
    setOpen(false);

    await mutateTemplate(
      value,
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
    if (!optionsMetaData?.[index]) return option;

    const metadata = optionsMetaData[index];
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
      const filtered = cloneDeep(validOptions);
      if (customValue === value && value && combobox) {
        filtered.push(customValue);
      }
      setFilteredOptions(filtered);
    }
  }, [open]);

  // Render helper functions

  const renderLoadingButton = () => (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
    >
      <LoadingTextComponent text="Loading options" />
    </Button>
  );

  const renderTriggerButton = () => (
    <ShadTooltip content={!value ? (tooltip as string) : ""}>
      <PopoverTrigger asChild>
        <Button
          disabled={
            disabled ||
            (Object.keys(validOptions).length === 0 &&
              !combobox &&
              !dialogInputs?.fields?.data?.node?.template)
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
            "w-full justify-between font-normal",
          )}
        >
          <span
            className="flex items-center gap-2 truncate"
            data-testid={`value-dropdown-${id}`}
          >
            {optionsMetaData?.[
              filteredOptions.findIndex((option) => option === value)
            ]?.icon && (
              <ForwardedIconComponent
                name={
                  optionsMetaData?.[
                    filteredOptions.findIndex((option) => option === value)
                  ]?.icon
                }
                className="h-4 w-4"
              />
            )}
            {value && filteredOptions.includes(value) ? value : placeholderName}{" "}
          </span>
          <ForwardedIconComponent
            name="ChevronsUpDown"
            className={cn(
              "ml-2 h-4 w-4 shrink-0 text-foreground",
              disabled
                ? "hover:text-placeholder-foreground"
                : "hover:text-foreground",
            )}
          />
        </Button>
      </PopoverTrigger>
    </ShadTooltip>
  );

  const renderSearchInput = () => (
    <div className="flex items-center border-b px-3">
      <ForwardedIconComponent
        name="search"
        className="mr-2 h-4 w-4 shrink-0 opacity-50"
      />
      <input
        onChange={searchRoleByTerm}
        placeholder="Search options..."
        className="flex h-9 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
        autoComplete="off"
      />
    </div>
  );

  const renderCustomOptionDialog = () => (
    <CommandGroup className="flex flex-col">
      <CommandItem className="flex cursor-pointer items-center justify-start gap-2 truncate py-3 text-xs font-semibold text-muted-foreground">
        <Button
          className="w-full"
          unstyled
          onClick={() => {
            setOpenDialog(true);
          }}
        >
          <div className="flex items-center gap-2 pl-1">
            <ForwardedIconComponent
              name="Plus"
              className="h-3 w-3 text-primary"
            />
            {`New ${firstWord}`}
          </div>
        </Button>
      </CommandItem>
      <CommandItem className="flex cursor-pointer items-center justify-start gap-2 truncate py-3 text-xs font-semibold text-muted-foreground">
        <Button
          className="w-full"
          unstyled
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
  );

  const renderOptionsList = () => (
    <CommandList>
      <CommandGroup defaultChecked={false}>
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
                  }}
                  className="items-center"
                  data-testid={`${option}-${index}-option`}
                >
                  <div className="flex w-full items-center gap-2">
                    {optionsMetaData && optionsMetaData.length > 0 && (
                      <ForwardedIconComponent
                        name={optionsMetaData?.[index]?.icon || "Unknown"}
                        className="h-4 w-4 shrink-0 text-primary"
                      />
                    )}
                    <div
                      className={cn("flex truncate", {
                        "flex-col":
                          optionsMetaData && optionsMetaData?.length > 0,
                        "w-full pl-2": !optionsMetaData?.[index]?.icon,
                      })}
                    >
                      <div className="flex truncate">
                        {option}{" "}
                        <span
                          className={`flex items-center pl-2 text-xs ${getStatusColor(
                            optionsMetaData?.[index]?.status,
                          )}`}
                        >
                          <LoadingTextComponent
                            text={optionsMetaData?.[
                              index
                            ]?.status?.toLowerCase()}
                          />
                        </span>
                      </div>
                      {optionsMetaData && optionsMetaData?.length > 0 ? (
                        <div className="flex w-full items-center text-muted-foreground">
                          {Object.entries(
                            filterMetadataKeys(optionsMetaData?.[index] || {}),
                          )
                            .filter(
                              ([key, value]) =>
                                value !== null && key !== "icon",
                            )
                            .map(([key, value], i, arr) => (
                              <div
                                key={key}
                                className={cn("flex items-center", {
                                  truncate: i === arr.length - 1,
                                })}
                              >
                                {i > 0 && (
                                  <ForwardedIconComponent
                                    name="Circle"
                                    className="mx-1 h-1 w-1 overflow-visible fill-muted-foreground"
                                  />
                                )}
                                <div
                                  className={cn("text-xs", {
                                    truncate: i === arr.length - 1,
                                  })}
                                >{`${String(value)} ${key}`}</div>
                              </div>
                            ))}
                        </div>
                      ) : (
                        <div className="ml-auto flex">
                          <ForwardedIconComponent
                            name="Check"
                            className={cn(
                              "h-4 w-4 shrink-0 text-primary",
                              value === option ? "opacity-100" : "opacity-0",
                            )}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </CommandItem>
              </div>
            </ShadTooltip>
          ))
        ) : (
          <CommandItem disabled className="text-center text-sm">
            No options found
          </CommandItem>
        )}
      </CommandGroup>
      <CommandSeparator />
      {dialogInputs && dialogInputs?.fields && renderCustomOptionDialog()}
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
      <Command>
        {filteredOptions?.length > 0 && renderSearchInput()}
        {renderOptionsList()}
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
      ) : (
        renderTriggerButton()
      )}
      {renderPopoverContent()}
    </Popover>
  );
}
