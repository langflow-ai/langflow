import { useState } from "react";
import { dropdownButtonPropsType } from "../../../types/components";
import IconComponent from "../../common/genericIconComponent";
import { Button } from "../../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../../ui/dropdown-menu";

export default function DropdownButton({
  firstButtonName,
  onFirstBtnClick,
  options,
  plusButton = false,
  dropdownOptions = true,
  isFetchingFolders = false,
}: dropdownButtonPropsType): JSX.Element {
  const [showOptions, setShowOptions] = useState<boolean>(false);

  return (
    <div>
      <DropdownMenu open={showOptions}>
        <DropdownMenuTrigger asChild>
          <Button
            id="new-project-btn"
            variant="primary"
            className={
              "relative" + dropdownOptions ? "pl-[12px]" : "pl-[12px] pr-10"
            }
            onClick={(event) => {
              event.stopPropagation();
              event.preventDefault();
              onFirstBtnClick();
            }}
            disabled={isFetchingFolders}
          >
            {plusButton && (
              <IconComponent name="Plus" className="main-page-nav-button" />
            )}
            {firstButtonName}
            {dropdownOptions && (
              <div
                className="absolute right-2 items-center text-muted-foreground"
                onClick={(event) => {
                  event.stopPropagation();
                  event.preventDefault();
                  setShowOptions(!showOptions);
                }}
              >
                {!showOptions ? (
                  <IconComponent name="ChevronDown" />
                ) : (
                  <IconComponent name="ChevronUp" />
                )}
              </div>
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          onPointerDownOutside={(event) => {
            event.stopPropagation();
            event.preventDefault();
            setShowOptions(!showOptions);
          }}
        >
          {options.map(({ name, onBtnClick }, index) => (
            <DropdownMenuItem onClick={onBtnClick} key={index}>
              {name}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
