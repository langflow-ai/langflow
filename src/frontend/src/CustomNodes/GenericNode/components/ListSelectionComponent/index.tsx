import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close";
import { Input } from "@/components/ui/input";
import { useState } from "react";
interface ListSelectionComponentProps {
  open: boolean;
  onClose: () => void;
  hasSearch?: boolean;
  setSelectedAction: (action: any[]) => void;
  selectedAction: any[];
  type: boolean;
}

const ListSelectionComponent = ({
  open,
  onClose,
  hasSearch = true,
  setSelectedAction = () => {},
  selectedAction = [],
  type,
}: ListSelectionComponentProps) => {
  const [search, setSearch] = useState("");

  const handleSelectAction = (action: any) => {
    if (type) {
      // Check if the action is already selected
      const isAlreadySelected = selectedAction.some(
        (selectedItem) => selectedItem.id === action.id,
      );

      if (isAlreadySelected) {
        // If already selected, remove it from the array
        setSelectedAction(
          selectedAction.filter(
            (selectedItem) => selectedItem.id !== action.id,
          ),
        );
      } else {
        // If not selected, add it to the array
        setSelectedAction([...selectedAction, action]);
      }
    } else {
      setSelectedAction([{ name: action?.name, icon: action?.icon }]);
      onClose();
    }
  };

  const handleCloseDialog = () => {
    onClose();
  };

  const initialActionData = [
    {
      name: "Accept a repository invitation",
      id: 1,
      metaData: "21 actions",
    },
    {
      name: "Add an email address for the repository",
      id: 2,
      metaData: "15 actions",
    },
    {
      name: "Add assignee to an issue",
      id: 3,
      metaData: "18 actions",
    },
    {
      name: "Create a new branch",
      id: 4,
      metaData: "12 actions",
    },
    {
      name: "Delete repository files",
      id: 5,
      metaData: "9 actions",
    },
    {
      name: "Fork a repository",
      id: 6,
      metaData: "24 actions",
    },
    {
      name: "Merge pull request",
      id: 7,
      metaData: "16 actions",
    },
    {
      name: "Review code changes",
      id: 8,
      metaData: "19 actions",
    },
    {
      name: "Update repository settings",
      id: 9,
      metaData: "27 actions",
    },
    {
      name: "Create repository webhook",
      id: 10,
      metaData: "13 actions",
    },
  ];

  const toolData = [
    {
      name: "Github",
      id: 1,
      icon: "github",
    },
    {
      name: "Microsoft",
      id: 2,
      icon: "microsoft",
    },
    {
      name: "Google",
      id: 3,
      icon: "google",
    },
    {
      name: "Slack",
      id: 4,
      icon: "slack",
    },
    {
      name: "Dropbox",
      id: 5,
      icon: "dropbox",
    },
  ];

  const listOfStuff = type ? initialActionData : toolData;

  return (
    <Dialog open={open} onOpenChange={handleCloseDialog}>
      <DialogContent>
        <div className="flex items-center justify-between">
          <div className="mr-10 flex w-full items-center rounded-md border">
            {hasSearch && (
              <button className="flex items-center gap-2 pl-4 text-sm">
                All
                <ForwardedIconComponent
                  name="chevron-down"
                  className="flex h-4 w-4"
                />
              </button>
            )}
            <Input
              icon="search"
              placeholder="Search tools..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              inputClassName="border-none focus:ring-0"
            />
          </div>

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
          {listOfStuff.map((action, index) => (
            <Button
              key={action.id}
              unstyled
              size="sm"
              className="w-full py-3"
              onClick={() => handleSelectAction(action)}
            >
              <div className="flex items-center gap-2">
                {action?.icon && (
                  <ForwardedIconComponent
                    name={action?.icon}
                    className="h-5 w-5"
                  />
                )}
                <span className="font-semibold">{action.name}</span>
                <span className="text-gray-500">{action.metaData}</span>
                {selectedAction.some(
                  (selectedItem) => selectedItem.id === action.id,
                ) && (
                  <ForwardedIconComponent
                    name="check"
                    className="ml-auto flex h-4 w-4"
                  />
                )}
              </div>
            </Button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ListSelectionComponent;
