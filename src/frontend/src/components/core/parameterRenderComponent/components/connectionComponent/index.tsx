import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "@/utils/utils";
import { memo, useEffect, useState } from "react";
import { InputProps } from "../../types";
import HelperTextComponent from "../helperTextComponent";

type ConnectionComponentProps = {
  tooltip?: string;
  name?: string;
  helperText?: string;
  helperMetadata?: any;
  options?: any[];
  searchCategory?: string[];
  buttonMetadata?: { variant?: string; icon?: string };
  connectionLink?: string;
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
  const { value, handleOnNewValue } = baseInputProps;

  const [isAuthenticated, setIsAuthenticated] = useState(
    connectionLink === "validated",
  );
  const [link, setLink] = useState("");
  const { placeholder } = baseInputProps;
  const [open, setOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any[]>([]);

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
    window.open(link, "_blank");
  };

  const handleSelection = (item: any) => {
    setIsAuthenticated(false);
    setLink("loading");
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
            loading={selectedItem?.length > 0 && value && link === "loading"}
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
