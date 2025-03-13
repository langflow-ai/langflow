import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "@/utils/utils";
import { memo, useCallback, useEffect, useState } from "react";
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
  connectionLink = "https://en.wikipedia.org/wiki/DataStax",
  ...baseInputProps
}: InputProps<any, ConnectionComponentProps>) => {
  const { value, handleOnNewValue } = baseInputProps;

  const { placeholder } = baseInputProps;
  const [open, setOpen] = useState(false);
  const [connectionButton, setConnectionButton] = useState(true);
  const [selectedItem, setSelectedItem] = useState<any[]>([]);

  const handleConnectionButtonClick = useCallback(() => {
    setConnectionButton((prev) => !prev);
    window.open(connectionLink, "_blank");
  }, []);

  const handleOpenListSelectionDialog = useCallback(() => setOpen(true), []);

  const handleCloseListSelectionDialog = useCallback(() => {
    setOpen(false);
  }, [value, selectedItem]);

  useEffect(() => {
    handleOnNewValue({ value: selectedItem[0]?.name }, { skipSnapshot: true });
  }, [selectedItem]);

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex w-full flex-row gap-2">
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
                className="mr-3 h-5 w-5"
              />
            )}
            {selectedItem[0]?.name || placeholder}
            <ForwardedIconComponent
              name="ChevronsUpDown"
              className="ml-auto h-5 w-5"
            />
          </div>
        </Button>

        {connectionButton && (
          <Button
            size="icon"
            disabled={!selectedItem[0]?.name}
            variant={buttonMetadata.variant as any}
            className={cn(
              "h-9 w-10 rounded-md border",
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
