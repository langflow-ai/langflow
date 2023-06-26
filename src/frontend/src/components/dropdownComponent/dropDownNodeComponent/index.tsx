import { Listbox, Transition } from "@headlessui/react";
import { Fragment, useContext, useEffect, useState } from "react";
import { INPUT_STYLE } from "../../../constants";
import { Check, ChevronsUpDown } from "lucide-react";
import { classNames } from "../../../utils";
import { PopUpContext } from "../../../contexts/popUpContext";
import { TabsContext } from "../../../contexts/tabsContext";

// Separate component for each dropdown node
export function DropdownNode({ value, options, onSelect }) {
  const [internalValue, setInternalValue] = useState(
    value === "" || !value ? "Choose an option" : value
  );

  useEffect(() => {
    setInternalValue(value === "" || !value ? "Choose an option" : value);
  }, [value]);

  const handleValueChange = (value) => {
    setInternalValue(value);
    onSelect(value);
  };

    return (
      <Listbox value={internalValue} onChange={handleValueChange}>
        {({ open }) => (
          <div className="relative mt-1">
            <Listbox.Button
              className={
                "ring-1 ring-slate-300 dark:ring-slate-600 w-full py-2 pl-3 pr-10 text-left dark:focus:ring-offset-2 dark:focus:ring-offset-gray-900 dark:focus:ring-1 dark:focus:ring-gray-600 dark:focus-visible:ring-gray-900 dark:focus-visible:ring-offset-2 focus-visible:outline-none dark:bg-gray-900 dark:text-gray-300 dark:border-gray-600 rounded-md border-gray-300 shadow-sm sm:text-sm " +
                INPUT_STYLE
              }
            >
              <span className="block truncate w-full">{internalValue}</span>
              <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
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
              <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto overflow-y rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
                {options.map((option, id) => (
                  <Listbox.Option
                    key={id}
                    className={({ active }) =>
                      classNames(
                        active
                          ? " bg-accent dark:bg-white dark:text-gray-500"
                          : "",
                        "relative cursor-default select-none py-2 pl-3 pr-9 dark:text-gray-300 dark:bg-gray-800"
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
  
                        {selected && (
                          <span className={classNames(
                            active ? "text-white dark:text-black" : "",
                            "absolute inset-y-0 right-0 flex items-center pr-4"
                          )}>
                            <Check
                              className={
                                active
                                  ? "h-5 w-5 dark:text-black text-black"
                                  : "h-5 w-5 dark:text-white text-black"
                              }
                              aria-hidden="true"
                            />
                          </span>
                        )}
                      </>
                    )}
                  </Listbox.Option>
                ))}
              </Listbox.Options>
            </Transition>
          </div>
        )}
      </Listbox>
    );
  }