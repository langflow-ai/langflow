import { useState } from "react";
import IconComponent from "../../../../components/genericIconComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import { Button } from "../../../../components/ui/button";
import { Checkbox } from "../../../../components/ui/checkbox";
import { cn } from "../../../../utils/utils";

type HeaderComponentProps = {
  handleSelectAll: (select) => void;
  handleDelete: () => void;
  handleDuplicate: () => void;
  handleExport: () => void;
  disableFunctions: boolean;
};

const HeaderComponent = ({
  handleSelectAll,
  handleDelete,
  handleDuplicate,
  handleExport,
  disableFunctions,
}: HeaderComponentProps) => {
  const [shouldSelectAll, setShouldSelectAll] = useState(true);

  const handleClick = () => {
    handleSelectAll(shouldSelectAll);
    setShouldSelectAll((prevState) => !prevState);
  };

  return (
    <>
      <div className="flex w-full items-center justify-between gap-4">
        <div className="flex items-center justify-self-start">
          <a onClick={handleClick} className="cursor-pointer text-sm">
            <div className="flex items-center space-x-2">
              <Checkbox checked={!shouldSelectAll} id="terms" />
              <span className="label text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                {shouldSelectAll ? "Select All" : "Unselect All"}
              </span>
            </div>
          </a>
        </div>
        <div className="flex items-center gap-2">
          <div>
            <ShadTooltip
              content={
                disableFunctions ? (
                  <span>Select items to export</span>
                ) : (
                  <span>Export selected items</span>
                )
              }
            >
              <Button
                unstyled
                onClick={handleExport}
                disabled={disableFunctions}
              >
                <IconComponent
                  name="FileDown"
                  className={cn("h-5 w-5 text-primary transition-all")}
                />
              </Button>
            </ShadTooltip>
          </div>
          <div>
            <ShadTooltip
              content={
                disableFunctions ? (
                  <span>Select items to duplicate</span>
                ) : (
                  <span>Duplicate selected items</span>
                )
              }
            >
              <Button
                unstyled
                onClick={handleDuplicate}
                disabled={disableFunctions}
              >
                <IconComponent
                  name="Copy"
                  className={cn("h-5 w-5 text-primary transition-all")}
                />
              </Button>
            </ShadTooltip>
          </div>
          <div>
            <ShadTooltip
              content={
                disableFunctions ? (
                  <span>Select items to delete</span>
                ) : (
                  <span>Delete selected items</span>
                )
              }
            >
              <Button
                unstyled
                onClick={handleDelete}
                disabled={disableFunctions}
              >
                <IconComponent
                  name="Trash2"
                  className={cn(
                    "h-5 w-5 text-primary transition-all",
                    disableFunctions ? "" : "hover:text-status-red",
                  )}
                />
              </Button>
            </ShadTooltip>
          </div>
        </div>
      </div>
    </>
  );
};
export default HeaderComponent;
