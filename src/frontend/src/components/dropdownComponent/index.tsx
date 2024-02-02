import { Listbox, Transition } from "@headlessui/react";
import { Fragment, useEffect, useState } from "react";
import { DropDownComponentType } from "../../types/components";
import { classNames } from "../../utils/utils";
import IconComponent from "../genericIconComponent";

export default function Dropdown({
  value,
  options,
  onSelect,
  editNode = false,
  numberOfOptions = 0,
  apiModal = false,
  id = "",
}: DropDownComponentType): JSX.Element {
  let [internalValue, setInternalValue] = useState(
    value === "" || !value ? "Choose an option" : value
  );

  useEffect(() => {
    setInternalValue(value === "" || !value ? "Choose an option" : value);
  }, [value]);

  return (
    <>
      {Object.keys(options)?.length > 0 ? (
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
                <div className={"relative mt-1"}>
                  <Listbox.Button
                    data-test={`${id ?? ""}`}
                    className={
                      editNode
                        ? "dropdown-component-outline"
                        : "dropdown-component-false-outline"
                    }
                  >
                    <span
                      className="dropdown-component-display"
                      data-testid={`${id ?? ""}-display`}
                    >
                      {internalValue}
                    </span>
                    <span className={"dropdown-component-arrow"}>
                      <IconComponent
                        name="ChevronsUpDown"
                        className="dropdown-component-arrow-color"
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
                          ? "dropdown-component-true-options nowheel custom-scroll"
                          : "dropdown-component-false-options nowheel custom-scroll",
                        apiModal ? "mb-2 w-[250px]" : "absolute w-full"
                      )}
                    >
                      {options?.map((option, id) => (
                        <Listbox.Option
                          key={id}
                          className={({ active }) =>
                            classNames(
                              active ? " bg-accent" : "",
                              editNode
                                ? "dropdown-component-false-option"
                                : "dropdown-component-true-option"
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
                                data-testid={`${option}-${id ?? ""}-option`}
                              >
                                {option}
                              </span>

                              {selected ? (
                                <span
                                  className={classNames(
                                    active ? "text-background " : "",
                                    "dropdown-component-choosal"
                                  )}
                                >
                                  <IconComponent
                                    name="Check"
                                    className={
                                      active
                                        ? "dropdown-component-check-icon"
                                        : "dropdown-component-check-icon"
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
      ) : (
        <>
          <div>
            <span className="text-sm italic">
              No parameters are available for display.
            </span>
          </div>
        </>
      )}
    </>
  );
}
