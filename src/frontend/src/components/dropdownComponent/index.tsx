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
                    ? "relative pr-8 placeholder:text-center block w-full pt-0.5 pb-0.5 form-input dark:bg-gray-900 dark:text-gray-300 dark:border-gray-600 rounded-md shadow-sm sm:text-sm border-gray-300 border-1" +
                      INPUT_STYLE
                    : "ring-1 ring-slate-300 dark:ring-slate-600 w-full py-2 pl-3 pr-10 text-left dark:focus:ring-offset-2 dark:focus:ring-offset-gray-900 dark:focus:ring-1 dark:focus:ring-gray-600 dark:focus-visible:ring-gray-900 dark:focus-visible:ring-offset-2 focus-visible:outline-none dark:bg-gray-900 dark:text-gray-300 dark:border-gray-600 rounded-md border-gray-300 shadow-sm sm:text-sm" +
                      INPUT_STYLE
                }
              >
                <span className="block truncate w-full">{internalValue}</span>
                <span
                  className={
                    "pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2"
                  }
                >
                  <ChevronsUpDown
                    className="h-5 w-5 text-gray-400"
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
                  className={
                    editNode
                      ? "absolute z-10 mt-1 max-h-60 overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm w-[215px]"
                      : "nowheel absolute z-10 mt-1 max-h-60 w-full overflow-auto overflow-y rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm "
                  }
                >
                  {options.map((option, id) => (
                    <Listbox.Option
                      key={id}
                      className={({ active }) =>
                        classNames(
                          active
                            ? " bg-accent dark:bg-white dark:text-gray-500"
                            : "",
                          editNode
                            ? "relative cursor-default select-none py-0.5 pl-3 pr-12 dark:text-gray-300 dark:bg-gray-800"
                            : "relative cursor-default select-none py-2 pl-3 pr-9 dark:text-gray-300 dark:bg-gray-800"
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
                                active ? "text-white dark:text-black" : "",
                                "absolute inset-y-0 right-0 flex items-center pr-4"
                              )}
                            >
                              <Check
                                className={
                                  active
                                    ? "h-5 w-5 dark:text-black text-black"
                                    : "h-5 w-5 dark:text-white text-black"
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
