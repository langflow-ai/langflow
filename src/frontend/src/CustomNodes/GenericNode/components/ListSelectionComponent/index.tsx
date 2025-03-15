import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SearchBarComponent from "@/components/core/parameterRenderComponent/components/searchBarComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close";
import { Input } from "@/components/ui/input";
import { useCallback, useMemo, useState } from "react";

// Define a union type for selection mode
type SelectionMode = "multiple" | "single";

// Update interface with better types
interface ListSelectionComponentProps {
  open: boolean;
  options: any[];
  onClose: () => void;
  setSelectedList: (action: any[]) => void;
  selectedList: any[];
  type: SelectionMode;
  searchCategories?: string[];
}

const ListItem = ({
  item,
  isSelected,
  onClick,
}: {
  item: any;
  isSelected: boolean;
  onClick: () => void;
}) => (
  <Button
    key={item.id}
    unstyled
    size="sm"
    className="w-full py-3"
    onClick={onClick}
  >
    <div className="flex items-center gap-2">
      {item.icon && (
        <ForwardedIconComponent name={item.icon} className="h-5 w-5" />
      )}
      <span className="font-semibold">{item.name}</span>
      {"metaData" in item && item.metaData && (
        <span className="text-gray-500">{item.metaData}</span>
      )}
      {isSelected && (
        <ForwardedIconComponent name="check" className="ml-auto flex h-4 w-4" />
      )}
    </div>
  </Button>
);

const ListSelectionComponent = ({
  open,
  onClose,
  searchCategories = [],
  setSelectedList = () => {},
  selectedList = [],
  type,
  options,
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
      if (type === "multiple") {
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
          setSelectedList([...selectedList, action]);
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
      }
    },
    [type, selectedList, setSelectedList, onClose],
  );

  const handleCloseDialog = useCallback(() => {
    onClose();
  }, [onClose]);

  return (
    <Dialog open={open} onOpenChange={handleCloseDialog}>
      <DialogContent>
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

        <div className="flex flex-col gap-1">
          {filteredList.length > 0 ? (
            filteredList.map((item) => (
              <ListItem
                key={item.name}
                item={item}
                isSelected={selectedList.some(
                  (selected) => selected.name === item.name,
                )}
                onClick={() => handleSelectAction(item)}
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
