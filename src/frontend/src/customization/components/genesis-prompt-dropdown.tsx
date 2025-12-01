/**
 * Genesis Prompt Dropdown Component
 *
 * A custom dropdown for the Genesis Prompt Template that includes
 * "Create new Prompt" option inside the dropdown menu (like "Refresh list").
 */

import { PopoverAnchor } from "@radix-ui/react-popover";
import Fuse from "fuse.js";
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { RECEIVING_INPUT_VALUE, SELECT_AN_OPTION } from "@/constants/constants";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import { cn, filterNullOptions } from "@/utils/utils";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import CreatePromptModal from "@/modals/createPromptModal";

interface GenesisPromptDropdownProps {
  id: string;
  value: string;
  editNode: boolean;
  handleOnNewValue: (data: any, options?: any) => void;
  disabled: boolean;
  nodeId: string;
  nodeClass: APIClassType;
  handleNodeClass: (value: any, code?: string, type?: string) => void;
  name: string;
  options: string[];
  optionsMetaData?: any[];
  placeholder?: string;
  combobox?: boolean;
  dialogInputs?: any;
  externalOptions?: any;
  toggle?: boolean;
  hasRefreshButton?: boolean;
}

export default function GenesisPromptDropdown({
  id,
  value,
  editNode,
  handleOnNewValue,
  disabled,
  nodeId,
  nodeClass,
  handleNodeClass,
  name,
  options,
  optionsMetaData,
  placeholder,
  combobox,
  hasRefreshButton,
}: GenesisPromptDropdownProps): JSX.Element {
  const validOptions = useMemo(() => filterNullOptions(options), [options]);
  const [open, setOpen] = useState(false);
  const [customValue, setCustomValue] = useState("");
  const [filteredOptions, setFilteredOptions] = useState(() => {
    if (value && !validOptions.includes(value) && combobox) {
      return [...validOptions, value];
    }
    return validOptions;
  });
  const [filteredMetadata, setFilteredMetadata] = useState(optionsMetaData);
  const [refreshOptions, setRefreshOptions] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const refButton = useRef<HTMLButtonElement>(null);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
  });

  const fuse = new Fuse(validOptions, { keys: ["name", "value"] });

  const onSelect = (selectedValue: string) => {
    handleOnNewValue({ value: selectedValue });
    setOpen(false);
  };

  useEffect(() => {
    if (open) {
      setFilteredOptions(validOptions);
      setFilteredMetadata(optionsMetaData);
    }
  }, [open, validOptions, optionsMetaData]);

  const searchRoleByTerm = (event: ChangeEvent<HTMLInputElement>) => {
    const searchValue = event.target.value;
    setCustomValue(searchValue);

    if (!searchValue) {
      setFilteredOptions(validOptions);
      setFilteredMetadata(optionsMetaData);
      return;
    }

    const searchValues = fuse.search(searchValue);
    const filtered = searchValues.map((search) => search.item);
    setFilteredOptions(filtered);

    if (optionsMetaData) {
      const metadataMap: Record<string, any> = {};
      validOptions.forEach((option, index) => {
        if (optionsMetaData[index]) {
          metadataMap[option] = optionsMetaData[index];
        }
      });
      const newMetadata = filtered.map((option) => metadataMap[option]);
      setFilteredMetadata(newMetadata);
    }
  };

  const handleRefreshButtonPress = async () => {
    setRefreshOptions(true);
    setOpen(false);

    await mutateTemplate(
      value,
      nodeId,
      nodeClass,
      handleNodeClass,
      postTemplateValue,
      setErrorData
    )?.then(() => {
      setTimeout(() => {
        setRefreshOptions(false);
      }, 2000);
    });
  };

  const handlePromptCreated = async (promptId: string) => {
    setShowCreateModal(false);
    setOpen(false);

    try {
      await mutateTemplate(
        promptId,
        nodeId,
        nodeClass,
        (newNode) => {
          const store = useFlowStore.getState();
          store.setNode(nodeId, (old) => ({
            ...old,
            data: {
              ...old.data,
              node: newNode,
            },
          }));
          handleNodeClass(newNode);
        },
        postTemplateValue,
        setErrorData,
        name
      );
      setSuccessData({ title: "Prompt created and selected!" });
    } catch (error) {
      console.error("Failed to refresh prompt list:", error);
      setErrorData({
        title: "Prompt created but failed to select",
        list: ["Please refresh the dropdown manually"],
      });
    }
  };

  const renderTriggerButton = () => (
    <PopoverTrigger asChild>
      <Button
        disabled={disabled}
        variant="outline"
        size="sm"
        role="combobox"
        ref={refButton}
        aria-expanded={open}
        data-testid={id}
        className={cn(
          editNode
            ? "dropdown-component-outline input-edit-node"
            : "dropdown-component-false-outline py-2",
          "no-focus-visible w-full justify-between font-normal disabled:bg-muted hover:border-secondary-border focus:border-secondary-border disabled:text-secondary-font"
        )}
      >
        <span className="flex w-full items-center gap-2 overflow-hidden">
          <span className="truncate">
            {disabled ? (
              RECEIVING_INPUT_VALUE
            ) : value && options?.includes(value) ? (
              value
            ) : (
              <span className="text-muted-foreground">
                {placeholder || SELECT_AN_OPTION}
              </span>
            )}
          </span>
        </span>
        <ForwardedIconComponent
          name={disabled ? "Lock" : "ChevronsUpDown"}
          className={cn(
            "ml-2 h-4 w-4 shrink-0 text-foreground",
            disabled
              ? "text-placeholder-foreground hover:text-placeholder-foreground"
              : "hover:text-foreground"
          )}
        />
      </Button>
    </PopoverTrigger>
  );

  const renderSearchInput = () => (
    <div className="flex items-center border-b px-2.5">
      <ForwardedIconComponent
        name="search"
        className="mr-2 h-4 w-4 shrink-0 opacity-50"
      />
      <input
        onChange={searchRoleByTerm}
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
          filteredOptions.map((option, index) => (
            <CommandItem
              key={index}
              value={option}
              onSelect={(currentValue) => {
                onSelect(currentValue);
              }}
              className="w-full items-center rounded-none"
              data-testid={`${option}-${index}-option`}
            >
              <div className="flex w-full items-center gap-2">
                <div className="flex w-full pl-2">
                  <div className="text-[13px] mr-2 whitespace-nowrap flex-shrink-0">
                    {option}
                  </div>
                </div>
                <div className="pl-2 ml-auto">
                  <ForwardedIconComponent
                    name="Check"
                    className={cn(
                      "h-4 w-4 shrink-0 text-primary",
                      value === option ? "opacity-100" : "opacity-0"
                    )}
                  />
                </div>
              </div>
            </CommandItem>
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
      {/* Create new Prompt option */}
      <CommandGroup className="p-0">
        <CommandItem
          className="flex w-full cursor-pointer items-center justify-start gap-2 truncate rounded-none py-2.5 text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
          onSelect={() => {
            setShowCreateModal(true);
          }}
          data-testid="dropdown-create-new-prompt"
        >
          <div className="flex items-center gap-2 pl-1 text-[13px] font-semibold">
            <ForwardedIconComponent name="Plus" className="h-3 w-3" />
            Create new Prompt
          </div>
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
              <ForwardedIconComponent name="RefreshCcw" className="h-3 w-3" />
              Refresh list
            </div>
          </CommandItem>
        )}
      </CommandGroup>
    </CommandList>
  );

  if (refreshOptions) {
    return (
      <Button
        className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
        variant="outline"
        size="xs"
      >
        <LoadingTextComponent text="Loading options" />
      </Button>
    );
  }

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <div className="w-full truncate">{renderTriggerButton()}</div>
        <PopoverContentWithoutPortal
          side="bottom"
          className="noflow nowheel nopan nodelete nodrag p-0"
          style={{ minWidth: refButton?.current?.clientWidth ?? "200px" }}
        >
          <Command className="flex flex-col">
            {options?.length > 0 && renderSearchInput()}
            {renderOptionsList()}
          </Command>
        </PopoverContentWithoutPortal>
      </Popover>

      <CreatePromptModal
        open={showCreateModal}
        setOpen={setShowCreateModal}
        onSuccess={handlePromptCreated}
      />
    </>
  );
}
