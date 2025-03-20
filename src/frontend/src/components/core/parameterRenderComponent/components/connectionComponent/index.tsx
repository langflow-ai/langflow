import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { APIClassType } from "@/types/api";
import { cn } from "@/utils/utils";
import { memo, useEffect, useRef, useState } from "react";
import { InputProps } from "../../types";
import HelperTextComponent from "../helperTextComponent";

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
  const { value, handleOnNewValue, nodeClass, nodeId } = baseInputProps;

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [isAuthenticated, setIsAuthenticated] = useState(
    connectionLink === "validated",
  );
  const [link, setLink] = useState("");
  const [isPolling, setIsPolling] = useState(false);
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  const pollingTimeout = useRef<NodeJS.Timeout | null>(null);
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const { placeholder } = baseInputProps;
  const [open, setOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any[]>([]);

  const setNodeClass = (newNode: APIClassType) => {
    const targetNode = nodes.find((node) => node.id === nodeId);
    if (!targetNode) return;

    targetNode.data.node = newNode;
    setNode(nodeId, targetNode);
  };

  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
  });

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (link === "loading") {
      timeoutId = setTimeout(() => {
        setLink("");
      }, 5000);
    }

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [link]);

  useEffect(() => {
    if (connectionLink !== "") {
      setLink(connectionLink);
      setIsAuthenticated(connectionLink === "validated");
    }
  }, [connectionLink]);

  const handleConnectionButtonClick = () => {
    if (selectedItem?.length === 0) return;

    window.open(link, "_blank");

    // Start polling
    setIsPolling(true);
    let attempts = 0;
    const maxAttempts = 5; // 35 seconds / 7 seconds = 5 attempts

    // Clear any existing intervals/timeouts
    if (pollingInterval.current) clearInterval(pollingInterval.current);
    if (pollingTimeout.current) clearTimeout(pollingTimeout.current);

    // Set up polling interval
    pollingInterval.current = setInterval(() => {
      attempts++;

      // Call mutateTemplate
      mutateTemplate(
        { validate: selectedItem[0]?.name || "" },
        nodeClass,
        setNodeClass,
        postTemplateValue,
        setErrorData,
        name,
        () => {},
        nodeClass.tool_mode,
      );

      // Check if connection is validated
      if (connectionLink === "validated" || link === "validated") {
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        setIsPolling(false);
        setIsAuthenticated(true);
        return;
      }

      // Stop polling after max attempts
      if (attempts >= maxAttempts) {
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        setIsPolling(false);
      }
    }, 7000);

    // Set timeout to stop polling after 30 seconds
    pollingTimeout.current = setTimeout(() => {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
      setIsPolling(false);
    }, 35000);
  };

  // Cleanup intervals and timeouts on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
      if (pollingTimeout.current) clearTimeout(pollingTimeout.current);
    };
  }, []);

  const handleSelection = (item: any) => {
    setIsAuthenticated(false);
    setLink("loading");
    setSelectedItem([item]);
    handleOnNewValue({ value: item.name }, { skipSnapshot: true });
  };

  const handleOpenListSelectionDialog = () => {
    setOpen(true);
  };

  const handleCloseListSelectionDialog = () => setOpen(false);

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

      {helperText && (
        <HelperTextComponent
          helperText={helperText}
          helperMetadata={helperMetadata}
        />
      )}
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
