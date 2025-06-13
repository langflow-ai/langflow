import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import { useEffect, useMemo, useRef, useState } from "react";
import ListSelectionComponent from "../../../../../CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "../../../../../utils/utils";
import { default as ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { InputProps } from "../../types";

export default function McpComponent({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
}: InputProps<string, any>): JSX.Element {
  const { data: mcpServers } = useGetMCPServers();
  const options = useMemo(
    () =>
      mcpServers?.map((server) => ({
        name: server.name,
        description:
          server.toolsCount === null
            ? "Loading..."
            : !server.toolsCount
              ? "No actions found"
              : `${server.toolsCount} action${server.toolsCount === 1 ? "" : "s"}`,
      })),
    [mcpServers],
  );
  const [open, setOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any[]>([]);

  // Initialize selected item from value on mount or value/options change
  useEffect(() => {
    const selectedOption = value
      ? options?.find((option) => option.name === value)
      : null;
    setSelectedItem(
      selectedOption ? [{ name: selectedOption.name }] : [{ name: "" }],
    );
    if (value !== selectedOption?.name) {
      handleOnNewValue({ value: "" }, { skipSnapshot: true });
    }
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

  const handleSuccess = (server: string) => {
    handleOnNewValue({ value: server });
    setOpen(false);
  };

  return (
    <div className="flex w-full flex-col gap-2">
      {options && (
        <>
          {options.length > 0 ? (
            <Button
              variant="primary"
              size="xs"
              role="combobox"
              onClick={handleOpenListSelectionDialog}
              className="dropdown-component-outline input-edit-node w-full py-2"
              data-testid="mcp-server-dropdown"
              disabled={disabled}
            >
              <div
                className={cn(
                  "flex w-full items-center justify-start text-sm font-normal",
                )}
              >
                <span className="truncate">
                  {selectedItem[0]?.name
                    ? selectedItem[0]?.name
                    : "Select a server..."}
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
        </>
      )}
      <AddMcpServerModal
        open={addOpen}
        setOpen={setAddOpen}
        onSuccess={handleSuccess}
      />
    </div>
  );
}
