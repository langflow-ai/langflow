import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SearchBarComponent from "@/components/core/parameterRenderComponent/components/searchBarComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close";
import { cn } from "@/utils/utils";
import { useCallback, useMemo, useState } from "react";

// Update interface with better types
interface ListSelectionComponentProps {
  open: boolean;
  options: any[];
  onClose: () => void;
  setSelectedList: (action: any[]) => void;
  selectedList: any[];
  searchCategories?: string[];
  onSelection?: (action: any) => void;
  limit?: number;
}

const ListItem = ({
  item,
  isSelected,
  onClick,
  className,
}: {
  item: any;
  isSelected: boolean;
  onClick: () => void;
  className?: string;
}) => (
  <Button
    key={item.id}
    unstyled
    size="sm"
    className={cn("w-full rounded-md py-3 pl-3 pr-3 hover:bg-muted", className)}
    onClick={onClick}
  >
    <div className="flex items-center gap-2">
      {item.icon && (
        <ForwardedIconComponent name={item.icon} className="h-5 w-5" />
      )}
      <span className="truncate font-semibold">{item.name}</span>
      {"metaData" in item && item.metaData && (
        <span className="text-gray-500">{item.metaData}</span>
      )}
      {isSelected ? (
        <ForwardedIconComponent
          name="check"
          className={cn(
            "ml-auto flex h-4 w-4",
            item.link === "validated" && "text-green-500",
          )}
        />
      ) : (
        <span className="ml-auto flex h-4 w-4" />
      )}
    </div>
  </Button>
);

const ListSelectionComponent = ({
  open,
  onClose,
  searchCategories = [],
  onSelection,
  setSelectedList = () => {},
  selectedList = [],
  options,
  limit = 1,
}: ListSelectionComponentProps) => {
  const [search, setSearch] = useState("");

  const filteredList = useMemo(() => {
    if (!search.trim()) {
      return options;
    }
    const searchTerm = search.toLowerCase();
    return options.filter((item) =>
      item.name.toLowerCase().includes(searchTerm),
    );
  }, [options, search]);

  const handleSelectAction = useCallback(
    (action: any) => {
      if (limit !== 1) {
        // Multiple selection mode
        const isAlreadySelected = selectedList.some(
          (selectedItem) => selectedItem.name === action.name,
        );

        if (isAlreadySelected) {
          setSelectedList(
            selectedList.filter(
              (selectedItem) => selectedItem.name !== action.name,
            ),
          );
        } else {
          // Check if we've reached the selection limit
          if (selectedList.length < limit) {
            setSelectedList([...selectedList, action]);
          }
        }
      } else {
        // Single selection mode
        setSelectedList([
          {
            name: action.name,
            icon: "icon" in action ? action.icon : undefined,
            link: "link" in action ? action.link : undefined,
          },
        ]);
        onClose();
        setSearch("");
      }
    },
    [selectedList, setSelectedList, onClose, limit],
  );

  const handleCloseDialog = useCallback(() => {
    onClose();
  }, [onClose]);

  return (
    <Dialog open={open} onOpenChange={handleCloseDialog}>
      <DialogContent className="flex !w-auto w-fit min-w-[20vw] max-w-[50vw] flex-col">
        <div className="flex items-center justify-between">
          <SearchBarComponent
            searchCategories={searchCategories}
            search={search}
            setSearch={setSearch}
          />
          <Button
            unstyled
            size="icon"
            className="ml-auto h-[38px]"
            onClick={handleCloseDialog}
          >
            <ForwardedIconComponent name="x" />
          </Button>
        </div>

        <div className="flex max-h-[80vh] flex-col gap-1 overflow-y-auto">
          {filteredList.length > 0 ? (
            filteredList.map((item, index) => (
              <ListItem
                key={`${item.name}-${index}`}
                item={item}
                isSelected={
                  selectedList.some(
                    (selected) => selected.name === item.name,
                  ) || item.link === "validated"
                }
                onClick={() => {
                  handleSelectAction(item);
                  onSelection?.(item);
                }}
              />
            ))
          ) : (
            <div className="py-3 text-center text-gray-500">
              No items match your search
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ListSelectionComponent;
