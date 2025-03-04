import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close";
import { Input } from "@/components/ui/input";
import { useState } from "react";
interface ListSelectionComponentProps {
  open: boolean;
  onClose: () => void;
  hasSearch?: boolean;
}

const ListSelectionComponent = ({
  open,
  onClose,
  hasSearch = true,
}: ListSelectionComponentProps) => {
  const [search, setSearch] = useState("");

  const handleSelectAction = () => {
    console.log("select action");
  };

  const handleCloseDialog = () => {
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleCloseDialog}>
      <DialogContent>
        <div className="flex items-center justify-between">
          {hasSearch && (
            <div className="mr-10 flex w-full items-center rounded-md border">
              <button className="flex items-center gap-2 pl-4 text-sm">
                All
                <ForwardedIconComponent
                  name="chevron-down"
                  className="flex h-4 w-4"
                />
              </button>
              <Input
                icon="search"
                placeholder="Search tools..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                inputClassName="border-none"
              />
            </div>
          )}
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
          {Array.from({ length: 3 }).map((_, index) => (
            <Button
              key={index}
              unstyled
              size="sm"
              className="w-full py-3"
              onClick={handleSelectAction}
            >
              <div className="flex items-center gap-2">
                <ForwardedIconComponent name="github" />
                <span className="font-semibold">Anthropic</span>
                <span className="text-gray-500">21 actions</span>
                <ForwardedIconComponent
                  name="check"
                  className="ml-auto flex h-4 w-4"
                />
              </div>
            </Button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ListSelectionComponent;
