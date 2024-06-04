import { useState } from "react";
import IconComponent from "../../../../components/genericIconComponent";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../../components/ui/select";
import { Checkbox } from "../../../../components/ui/checkbox";
import { Button } from "../../../../components/ui/button";
import { cn } from "../../../../utils/utils";
import ShadTooltip from "../../../../components/shadTooltipComponent";

type HeaderComponentProps = {
  handleSelectAll: (select) => void;
  handleDelete: () => void;
  disableDelete: boolean;
};

const HeaderComponent = ({
  handleSelectAll,
  handleDelete,
  disableDelete,
}: HeaderComponentProps) => {
  const [shouldSelectAll, setShouldSelectAll] = useState(true);

  const handleClick = () => {
    handleSelectAll(shouldSelectAll);
    setShouldSelectAll((prevState) => !prevState);
  };

  return (
    <>
      <div className="grid grid-cols-3 pb-5">
        <div className="col-auto grid-cols-1 self-center justify-self-start">
          <a onClick={handleClick} className="text-sm">
            <div className="header-menu-bar-display ">
              <div
                className="header-menu-flow-name"
                data-testid="select_all_collection"
              >
                <div className="flex items-center space-x-2">
                  <Checkbox checked={!shouldSelectAll} id="terms" />
                  <label
                    onClick={handleClick}
                    htmlFor="terms"
                    className="label cursor-pointer text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    {shouldSelectAll ? "Select All" : "Unselect All"}
                  </label>
                </div>
              </div>
            </div>
          </a>
        </div>
        <div className="col-span-2 grid-cols-1 justify-self-end">
          <div>
            <ShadTooltip
              content={
                disableDelete ? (
                  <span>Select items to delete</span>
                ) : (
                  <span>Delete selected items</span>
                )
              }
            >
              <button onClick={handleDelete} disabled={disableDelete}>
                <IconComponent
                  name="Trash2"
                  className={cn(
                    "h-5 w-5 text-primary transition-all",
                    disableDelete ? "" : "hover:text-destructive",
                  )}
                />
              </button>
            </ShadTooltip>
          </div>
        </div>
      </div>
    </>
  );
};
export default HeaderComponent;
