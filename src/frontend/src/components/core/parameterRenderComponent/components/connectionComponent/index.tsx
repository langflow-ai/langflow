import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useAlertStore from "@/stores/alertStore";
import { APIClassType } from "@/types/api";
import { cn } from "@/utils/utils";
import { memo, useEffect, useRef, useState } from "react";
import { InputProps } from "../../types";
import HelperTextComponent from "../helperTextComponent";

// Type definitions for component props
type ConnectionComponentProps = {
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
  // Destructure base props
  const {
    value,
    handleOnNewValue,
    handleNodeClass,
    nodeClass,
    nodeId,
    placeholder,
  } = baseInputProps;

  // Store access
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // State management
  const [isAuthenticated, setIsAuthenticated] = useState(
    connectionLink === "validated",
  );
  const [link, setLink] = useState("");
  const [isPolling, setIsPolling] = useState(false);
  const [open, setOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any[]>([]);

  // Refs for polling management
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  const pollingTimeout = useRef<NodeJS.Timeout | null>(null);

  // API hooks
  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
  });

  // Effects
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    if (link === "loading") {
      timeoutId = setTimeout(() => setLink(""), 5000);
    }
    return () => timeoutId && clearTimeout(timeoutId);
  }, [link]);

  useEffect(() => {
    if (connectionLink !== "") {
      setLink(connectionLink);
      setIsAuthenticated(connectionLink === "validated");
    }
  }, [connectionLink]);

  // Cleanup effect for polling
  useEffect(() => {
    return () => {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
      if (pollingTimeout.current) clearTimeout(pollingTimeout.current);
    };
  }, []);

  // Event handlers
  const handleConnectionButtonClick = () => {
    if (selectedItem?.length === 0) return;
    window.open(link, "_blank");

    // Initialize polling
    setIsPolling(true);
    let attempts = 0;
    const maxAttempts = 5;

    // Clear existing timers
    if (pollingInterval.current) clearInterval(pollingInterval.current);
    if (pollingTimeout.current) clearTimeout(pollingTimeout.current);

    // Set up polling interval
    pollingInterval.current = setInterval(() => {
      attempts++;
      mutateTemplate(
        { validate: selectedItem[0]?.name || "" },
        nodeClass,
        handleNodeClass,
        postTemplateValue,
        () => {},
        name,
        () => {},
        nodeClass.tool_mode,
      );

      if (connectionLink === "validated" || link === "validated") {
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        setIsPolling(false);
        setIsAuthenticated(true);
        return;
      }

      if (attempts >= maxAttempts) {
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        setIsPolling(false);
      }
    }, 7000);

    // Set timeout to stop polling
    pollingTimeout.current = setTimeout(() => {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
      setIsPolling(false);
    }, 35000);
  };

  const handleSelection = (item: any) => {
    setIsAuthenticated(false);
    setLink("loading");
    setSelectedItem([item]);
    handleOnNewValue({ value: item.name }, { skipSnapshot: true });
  };

  const handleOpenListSelectionDialog = () => setOpen(true);
  const handleCloseListSelectionDialog = () => setOpen(false);

  // Render component
  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex w-full flex-row items-center gap-2">
        {/* Selection Button */}
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

        {/* Connection Button */}
        {!isAuthenticated && (
          <Button
            size="icon"
            variant="ghost"
            loading={
              selectedItem?.length > 0 &&
              ((value && link === "loading") || isPolling)
            }
            disabled={!selectedItem[0]?.name || link === ""}
            className={cn(
              "h-9 w-10 rounded-md border disabled:opacity-50",
              buttonMetadata.variant && `border-${buttonMetadata.variant}`,
            )}
            onClick={handleConnectionButtonClick}
          >
            <ForwardedIconComponent
              name={buttonMetadata.icon || "unplug"}
              className={cn(
                "h-5 w-5",
                buttonMetadata.variant && `text-${buttonMetadata.variant}`,
              )}
            />
          </Button>
        )}
      </div>

      {/* Helper Text */}
      {helperText && (
        <HelperTextComponent
          helperText={helperText}
          helperMetadata={helperMetadata}
        />
      )}

      {/* List Selection Dialog */}
      <ListSelectionComponent
        open={open}
        onSelection={handleSelection}
        onClose={handleCloseListSelectionDialog}
        searchCategories={searchCategory}
        setSelectedList={setSelectedItem}
        selectedList={selectedItem}
        options={options}
        type="single"
      />
    </div>
  );
};

export default memo(ConnectionComponent);
