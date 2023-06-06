import { Listbox, Transition } from "@headlessui/react";
import { ChevronUpDownIcon, CheckIcon } from "@heroicons/react/24/outline";
import { Fragment, useState } from "react";
import { DropDownComponentType } from "../../types/components";
import { classNames } from "../../utils";

export default function Dropdown({
  value,
  options,
  onSelect,
}: DropDownComponentType) {
  let [internalValue, setInternalValue] = useState(
    value === "" || !value ? "Choose an option" : value
  );
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
            <div className="relative mt-1 w-full">
              <Listbox.Button className="relative w-full cursor-default rounded-md border border-gray-300 bg-white dark:bg-gray-900 py-2 pl-3 pr-10 text-left shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm">
                <span className="block truncate w-full dark:text-gray-300">
                  {internalValue}
                </span>
                <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                  <ChevronUpDownIcon
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
                <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full dark:bg-gray-800 overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
                  {options.map((option, id) => (
                    <Listbox.Option
                      key={id}
                      className={({ active }) =>
                        classNames(
                          active
                            ? "text-white bg-indigo-600 dark:bg-indigo-500"
                            : "text-gray-900",
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
                              "block truncate"
                            )}
                          >
                            {option}
                          </span>

                          {selected ? (
                            <span
                              className={classNames(
                                active ? "text-white" : "text-indigo-600",
                                "absolute inset-y-0 right-0 flex items-center pr-4"
                              )}
                            >
                              <CheckIcon
                                className="h-5 w-5"
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
