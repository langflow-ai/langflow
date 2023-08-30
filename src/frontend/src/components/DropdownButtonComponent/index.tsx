import { Fragment, useState } from "react";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { dropdownButtonPropsType } from "../../types/components";
import { Transition } from "@headlessui/react";

export default function DropdownButton({
  firstButtonName,
  onFirstBtnClick,
  options,
}: dropdownButtonPropsType): JSX.Element {
  const [showOptions, setShowOptions] = useState<boolean>(false);

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
      <Transition
        show={showOptions}
        leave="transition ease-in duration-100"
        leaveFrom="opacity-100"
        leaveTo="opacity-0"
        as={Fragment}
        enter="transition ease-in duration-100"
        enterFrom="opacity-0"
        enterTo="opacity-100"
      >
        <div className="absolute top-10 w-full bg-background pb-0.5 pr-0.5 pl-0.5 rounded-lg shadow-lg ">
          {options.map(({ name, onBtnClick }, index) => (
            <Button
              className="w-full mt-1"
              variant="primary"
              onClick={onBtnClick}
              key={index}
            >
              {name}
            </Button>
          ))}
        </div>
      </Transition>
    </div>
  );
}
