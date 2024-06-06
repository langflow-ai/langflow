import { useState } from "react";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/genericIconComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import { Checkbox } from "../../../../components/ui/checkbox";
import { cn } from "../../../../utils/utils";
import { Button } from "../../../../components/ui/button";

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
      <div className="grid grid-cols-3 pb-5">
        <div className="flex items-center gap-4 justify-self-start">
          <Button
            variant="outline"
            size="sm"
            onClick={handleClick}
            className="text-sm"
          >
            <ForwardedIconComponent
              name="FileUp"
              className="h-5 w-5 text-primary"
            />
            Upload Flow
          </Button>
          <Button
            variant="none"
            size="none"
            onClick={handleClick}
            className="text-sm"
          >
            <div className="flex items-center space-x-2">
              <Checkbox checked={!shouldSelectAll} id="terms" />
              <span className="label text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                {shouldSelectAll ? "Select All" : "Unselect All"}
              </span>
            </div>
          </Button>
        </div>
        <div className="col-span-2 flex grid-cols-1 gap-2 justify-self-end">
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
                variant="none"
                size="none"
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
                variant="none"
                size="none"
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
                variant="none"
                size="none"
                onClick={handleDelete}
                disabled={disableFunctions}
              >
                <IconComponent
                  name="Trash2"
                  className={cn(
                    "h-5 w-5 text-primary transition-all",
                    disableFunctions ? "" : "hover:text-destructive",
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
