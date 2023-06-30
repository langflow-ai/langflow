import { Listbox, Transition } from "@headlessui/react";
import { Fragment, useContext, useEffect, useState } from "react";
import { DropDownComponentType } from "../../types/components";
import { classNames } from "../../utils";
import { INPUT_STYLE } from "../../constants";
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
                    ? "relative pr-8 placeholder:text-center block w-full pt-0.5 pb-0.5 form-input rounded-md shadow-sm sm:text-sm border-ring border-1" +
                      INPUT_STYLE
                    : "ring-1 ring-ring placeholder:text-muted-foreground w-full py-2 pl-3 pr-10 text-left focus-visible:outline-none rounded-md border-ring shadow-sm sm:text-sm bg-background" +
                      INPUT_STYLE
                }
              >
                <span className="block bg-background truncate w-full">
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
                      ? "z-10 mt-1 max-h-60 overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm w-[215px]"
                      : "nowheel z-10 mt-1 max-h-60 w-full overflow-auto overflow-y rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm ",
                    apiModal ? "w-[250px] mb-2" : "absolute"
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
