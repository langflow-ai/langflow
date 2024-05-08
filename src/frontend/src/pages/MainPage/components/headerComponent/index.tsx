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

type HeaderComponentProps = {
  handleSelectAll: (select) => void;
  handleSelectOptionsChange: (option) => void;
};

const HeaderComponent = ({
  handleSelectAll,
  handleSelectOptionsChange,
}: HeaderComponentProps) => {
  const [shouldSelectAll, setShouldSelectAll] = useState(true);
  const [value, setValue] = useState("");

  const handleClick = () => {
    handleSelectAll(shouldSelectAll);
    setShouldSelectAll((prevState) => !prevState);
  };

  return (
    <>
      <div className="grid grid-cols-3 pb-5">
        <div className="col-auto grid-cols-1 self-center justify-self-start ">
          <a onClick={handleClick} className="text-sm">
            <div className="header-menu-bar-display ">
              <div
                className="header-menu-flow-name"
                data-testid="select_all_collection"
              >
                {shouldSelectAll ? "Select All" : "Unselect All"}
              </div>
            </div>
          </a>
        </div>
        <div className="col-span-2 grid-cols-1 justify-self-end">
          <div>
            <Select
              value={value}
              onValueChange={(e) => {
                handleSelectOptionsChange(e);
                setValue("");
              }}
            >
              <SelectTrigger className="w-[140px] flex-shrink-0">
                <SelectValue placeholder="Actions" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup className="right-6">
                  <SelectItem
                    value={"delete"}
                    className="cursor-pointer focus:bg-red-400/[.20]"
                  >
                    <div className="font-red flex text-status-red">
                      <IconComponent
                        name="Trash2"
                        className="relative top-0.5 mr-2 h-4 w-4 "
                      />{" "}
                      <span>Delete</span>
                    </div>
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
    </>
  );
};
export default HeaderComponent;
