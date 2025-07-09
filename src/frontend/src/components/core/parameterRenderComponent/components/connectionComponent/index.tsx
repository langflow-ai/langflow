import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useAlertStore from "@/stores/alertStore";
import type { APIClassType } from "@/types/api";
import { cn } from "@/utils/utils";
import { memo, useEffect, useRef, useState } from "react";
import type { InputProps } from "../../types";
import HelperTextComponent from "../helperTextComponent";

export type ConnectionComponentProps = {
  tooltip?: string;
  name: string;
  helperText?: string;
  helperMetadata?: any;
  options?: any[];
  searchCategory?: string[];
  buttonMetadata?: { variant?: string; icon?: string };
  connectionLink?: string;
  nodeClass: APIClassType;
  nodeId: string;
};

const ConnectionComponent = ({
  tooltip = "",
  name,
  helperText = "",
  helperMetadata = { icon: undefined, variant: "muted-foreground" },
  options = [],
  searchCategory = [],
  buttonMetadata = { variant: "destructive", icon: "unplug" },
  connectionLink = "",
  ...baseInputProps
}: InputProps<any, ConnectionComponentProps>) => {
  const {
    value,
    handleOnNewValue,
    handleNodeClass,
    nodeClass,
    nodeId,
    placeholder,
  } = baseInputProps;

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [isAuthenticated, setIsAuthenticated] = useState(
    connectionLink === "validated",
  );
  const [link, setLink] = useState("");
  const [isPolling, setIsPolling] = useState(false);
  const [open, setOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any[]>([]);

  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  const pollingTimeout = useRef<NodeJS.Timeout | null>(null);

  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
  });

  // Initialize selected item from value on component mount
  useEffect(() => {
    const selectedOption = value
      ? options.find((option) => option.name === value)
      : null;
    setSelectedItem([
      selectedOption
        ? { name: selectedOption.name, icon: selectedOption.icon }
        : { name: "", icon: "" },
    ]);

    // Update authentication status based on selected option
    if (!selectedOption) {
      setIsAuthenticated(false);
    }
  }, [value, options]);

  useEffect(() => {
    if (connectionLink !== "") {
      setLink(connectionLink);
      if (connectionLink === "validated") {
        setIsAuthenticated(true);
      }
    }

    if (connectionLink === "error") {
      setLink("error");
    }
  }, [connectionLink]);

  // Handles the connection button click to open connection in new tab and start polling
  const handleConnectionButtonClick = () => {
    if (selectedItem?.length === 0) return;

    customOpenNewTab(link);

    startPolling();
  };

  // Initiates polling to check connection status periodically
  const startPolling = () => {
    if (!selectedItem[0]?.name) return;

    setLink("loading");

    // Initialize polling
    setIsPolling(true);

    // Clear existing timers
    stopPolling();

    // Set up polling interval - check connection status every 3 seconds
    pollingInterval.current = setInterval(() => {
      mutateTemplate(
        { validate: selectedItem[0]?.name || "" },
        nodeId,
        nodeClass,
        handleNodeClass,
        postTemplateValue,
        setErrorData,
        name,
        () => {
          // Check if the connection was successful
          if (connectionLink === "validated") {
            stopPolling();
            setIsAuthenticated(true);
          }
        },
        nodeClass.tool_mode,
      );
    }, 3000);

    // Set timeout to stop polling after 9 seconds to prevent indefinite polling
    pollingTimeout.current = setTimeout(() => {
      stopPolling(link !== "");
      // If we timed out and link is still loading, reset it
    }, 9000);
  };

  // Cleans up polling timers to prevent memory leaks
  const stopPolling = (resetLink = false) => {
    setIsPolling(false);
    if (resetLink) {
      setLink(connectionLink || "");
    }

    if (pollingInterval.current) clearInterval(pollingInterval.current);
    if (pollingTimeout.current) clearTimeout(pollingTimeout.current);
  };

  // Updates selected item and triggers parent component update
  const handleSelection = (item: any) => {
    setIsAuthenticated(false);
    setSelectedItem([{ name: item.name }]);
    setLink(item.link === "validated" ? "validated" : "loading");
    if (item.link === "validated") {
      setIsAuthenticated(true);
    }
    handleOnNewValue({ value: item.name }, { skipSnapshot: true });
  };

  // Dialog control handlers
  const handleOpenListSelectionDialog = () => setOpen(true);
  const handleCloseListSelectionDialog = () => setOpen(false);

  // Render component
  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex w-full flex-row items-center gap-2">
        <Button
          variant="primary"
          size="xs"
          role="combobox"
          onClick={handleOpenListSelectionDialog}
          className="dropdown-component-outline input-edit-node w-full py-2"
        >
          <div className={cn("flex w-full items-center justify-start text-sm")}>
            {selectedItem[0]?.icon && (
              <ForwardedIconComponent
                name={selectedItem[0]?.icon}
                className="h-5 w-5"
              />
            )}
            <span className="ml-2 truncate">
              {selectedItem[0]?.name || placeholder}
            </span>
            <ForwardedIconComponent
              name="ChevronsUpDown"
              className="ml-auto h-5 w-5"
            />
          </div>
        </Button>

        {!isAuthenticated && (
          <Button
            size="icon"
            variant="ghost"
            loading={link === "loading" || isPolling}
            disabled={!selectedItem[0]?.name || link === "" || link === "error"}
            className={cn(
              "h-9 w-10 rounded-md border disabled:opacity-50",
              buttonMetadata.variant && `border-${buttonMetadata.variant}`,
            )}
            onClick={link === "error" ? undefined : handleConnectionButtonClick}
          >
            <ForwardedIconComponent
              name={
                link === "error"
                  ? "triangle-alert"
                  : buttonMetadata.icon || "unplug"
              }
              className={cn(
                "h-5 w-5",
                buttonMetadata.variant && `text-${buttonMetadata.variant}`,
              )}
            />
          </Button>
        )}
      </div>

      {helperText && (
        <HelperTextComponent
          helperText={helperText}
          helperMetadata={helperMetadata}
        />
      )}

      <ListSelectionComponent
        open={open}
        onClose={handleCloseListSelectionDialog}
        onSelection={handleSelection}
        searchCategories={searchCategory}
        setSelectedList={setSelectedItem}
        selectedList={selectedItem}
        options={options}
        {...baseInputProps}
      />
    </div>
  );
};

export default memo(ConnectionComponent);
