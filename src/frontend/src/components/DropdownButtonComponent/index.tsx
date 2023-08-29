import { useState } from "react";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";

export default function DropdownButton({
  firstButtonName,
  onFirstBtnClick,
  options,
}): JSX.Element {
  const [showOptions, setShowOptions] = useState(false);

  return (
    <div className="align-center relative flex">
      <div>
        <Button
          variant="primary"
          className="mr-4 w-full"
          onClick={onFirstBtnClick}
        >
          {firstButtonName}
        </Button>
      </div>
      <div>
        <button
          className="absolute inset-y-0 right-0 items-center text-muted-foreground"
          onClick={(event) => {
            event.stopPropagation();
            setShowOptions(!showOptions);
          }}
        >
          {!showOptions ? (
            <IconComponent name="ChevronDown" className="" aria-hidden="true" />
          ) : (
            <IconComponent name="ChevronUp" />
          )}
        </button>
      </div>
      {showOptions && (
        <div className="absolute top-10 w-full">
          {options.map(({ name, onBtnClick }) => (
            <Button
              className="w-full"
              variant="primary"
              onClick={onBtnClick}
              key={name}
            >
              {name}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
