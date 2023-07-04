import { Listbox, Transition } from "@headlessui/react";
import { Fragment, useContext, useEffect, useState } from "react";
import { DropDownComponentType } from "../../types/components";
import { classNames } from "../../utils";
import { ChevronsUpDown, Check } from "lucide-react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";

export default function Dropdown({
  value,
  options,
  onSelect,
  editNode = false,
  numberOfOptions = 0,
  apiModal = false,
}: DropDownComponentType) {
  const { closePopUp } = useContext(PopUpContext);

  let [internalValue, setInternalValue] = useState(
    value === "" || !value ? "Choose an option" : value
  );

  useEffect(() => {
    setInternalValue(value === "" || !value ? "Choose an option" : value);
  }, [closePopUp]);

  return (
    <>
      <Listbox
        value={internalValue}
        onChange={(value) => {
          setInternalValue(value);
          onSelect(value);
        }}
      >
        {({ open }) => (
          <>
            <div className={editNode ? "mt-1" : "relative mt-1"}>
              <Listbox.Button
                className={
                  editNode
                    ? "border-1 relative pr-8 input-edit-node"
                    : "py-2 pl-3 pr-10 text-left input-primary"
                }
              >
                <span className="block w-full truncate bg-background">
                  {internalValue}
                </span>
                <span
                  className={
                    "pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2"
                  }
                >
                  <ChevronsUpDown
                    className="h-5 w-5 text-muted-foreground"
                    aria-hidden="true"
                  />
                </span>
              </Listbox.Button>

              <Transition
                show={open}
                as={Fragment}
                leave="transition ease-in duration-100"
                leaveFrom="opacity-100"
                leaveTo="opacity-0"
              >
                <Listbox.Options
                  className={classNames(
                    editNode
                      ? "z-10 mt-1 max-h-60 w-[215px] overflow-auto rounded-md bg-background py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm"
                      : "nowheel overflow-y z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-background py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm ",
                    apiModal ? "mb-2 w-[250px]" : "absolute"
                  )}
                >
                  {options.map((option, id) => (
                    <Listbox.Option
                      key={id}
                      className={({ active }) =>
                        classNames(
                          active ? " bg-accent" : "",
                          editNode
                            ? "relative cursor-default select-none py-0.5 pl-3 pr-12"
                            : "relative cursor-default select-none py-2 pl-3 pr-9"
                        )
                      }
                      value={option}
                    >
                      {({ selected, active }) => (
                        <>
                          <span
                            className={classNames(
                              selected ? "font-semibold" : "font-normal",
                              "block truncate "
                            )}
                          >
                            {option}
                          </span>

                          {selected ? (
                            <span
                              className={classNames(
                                active ? "text-background " : "",
                                "absolute inset-y-0 right-0 flex items-center pr-4"
                              )}
                            >
                              <Check
                                className={
                                  active
                                    ? "h-5 w-5 text-black"
                                    : "h-5 w-5 text-black"
                                }
                                aria-hidden="true"
                              />
                            </span>
                          ) : null}
                        </>
                      )}
                    </Listbox.Option>
                  ))}
                </Listbox.Options>
              </Transition>
            </div>
          </>
        )}
      </Listbox>
    </>
  );
}
