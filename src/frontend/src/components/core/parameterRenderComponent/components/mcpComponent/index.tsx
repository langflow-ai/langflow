import AddMcpServerModal from "@/modals/addMcpServerModal";
import { useEffect, useRef, useState } from "react";
import ListSelectionComponent from "../../../../../CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "../../../../../utils/utils";
import { default as ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { InputProps } from "../../types";

const options = [
  {
    name: "lf-my_mcp_pawdio",
    icon: "Box",
    description: "23 actions",
  },
  {
    name: "lf-new_project",
    icon: "Box",
    description: "4 actions",
  },
];
export default function McpComponent({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
}: InputProps<string, any>): JSX.Element {
  // Example options, replace with real options as needed

  const [open, setOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any[]>([]);

  // Initialize selected item from value on mount or value/options change
  useEffect(() => {
    const selectedOption = value
      ? options.find((option) => option.name === value)
      : null;
    setSelectedItem(
      selectedOption ? [{ name: selectedOption.name }] : [{ name: "" }],
    );
  }, [value, options]);

  // Handle selection from dialog
  const handleSelection = (item: any) => {
    setSelectedItem([{ name: item.name }]);
    handleOnNewValue({ value: item.name }, { skipSnapshot: true });
    setOpen(false);
  };

  const handleAddButtonClick = () => {
    setAddOpen(true);
  };

  const handleOpenListSelectionDialog = () => setOpen(true);
  const handleCloseListSelectionDialog = () => setOpen(false);

  return (
    <div className="flex w-full flex-col gap-2">
      {options.length > 0 ? (
        <Button
          variant="primary"
          size="xs"
          role="combobox"
          onClick={handleOpenListSelectionDialog}
          className="dropdown-component-outline input-edit-node w-full py-2"
          disabled={disabled}
        >
          <div
            className={cn(
              "flex w-full items-center justify-start text-sm font-normal",
            )}
          >
            <span className="truncate">
              {selectedItem[0]?.name ? (
                <span className="flex items-center gap-2">
                  <ForwardedIconComponent
                    name="Box"
                    className="h-4 w-4 text-muted-foreground"
                  />
                  {selectedItem[0]?.name}
                </span>
              ) : (
                "Select a server..."
              )}
            </span>
            <ForwardedIconComponent
              name="ChevronsUpDown"
              className="ml-auto h-5 w-5 text-muted-foreground"
            />
          </div>
        </Button>
      ) : (
        <Button size="sm" onClick={handleAddButtonClick}>
          <span>Add MCP Server</span>
        </Button>
      )}
      <ListSelectionComponent
        open={open}
        onClose={handleCloseListSelectionDialog}
        onSelection={handleSelection}
        setSelectedList={setSelectedItem}
        selectedList={selectedItem}
        options={options}
        limit={1}
        id={id}
        value={value}
        editNode={editNode}
        headerSearchPlaceholder="Search MCP Servers..."
        handleOnNewValue={handleOnNewValue}
        disabled={disabled}
        addButtonText="Add MCP Server"
        onAddButtonClick={handleAddButtonClick}
      />
      <AddMcpServerModal open={addOpen} setOpen={setAddOpen} />
    </div>
  );
}
