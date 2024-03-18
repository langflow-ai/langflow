import { Listbox, Transition } from "@headlessui/react";
import * as Form from "@radix-ui/react-form";
import { Fragment, useEffect, useRef, useState } from "react";
import AddNewVariableButton from "../../pages/globalVariablesPage/components/addNewVariableButton";
import { InputComponentType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { classNames, cn } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Input } from "../ui/input";
import { Separator } from "../ui/separator";

export default function InputComponent({
  autoFocus = false,
  onBlur,
  value,
  onChange,
  disabled,
  required = false,
  isForm = false,
  password,
  editNode = false,
  placeholder = "Type something...",
  className,
  id = "",
  blurOnEnter = false,
  options = [],
}: InputComponentType): JSX.Element {
  const [pwdVisible, setPwdVisible] = useState(false);
  const refInput = useRef<HTMLInputElement>(null);
  const [showOptions, setShowOptions] = useState<boolean>(false);

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("");
    }
  }, [disabled]);

  const filteredOptions = options.filter((option) =>
    option.toLowerCase().includes(value.toLowerCase())
  );

  function onInputLostFocus(event): void {
    if (onBlur) onBlur(event);
  }

  return (
    <div className="relative w-full">
      {isForm ? (
        <Form.Control asChild>
          <Input
            id={"form-" + id}
            ref={refInput}
            onBlur={onInputLostFocus}
            autoFocus={autoFocus}
            type={password && !pwdVisible ? "password" : "text"}
            value={value}
            disabled={disabled}
            required={required}
            className={classNames(
              password && !pwdVisible && value !== ""
                ? " text-clip password "
                : "",
              editNode ? " input-edit-node " : "",
              password && editNode ? "pr-8" : "",
              password && !editNode ? "pr-10" : "",
              className!
            )}
            placeholder={password && editNode ? "Key" : placeholder}
            onChange={(e) => {
              onChange(e.target.value);
            }}
            onCopy={(e) => {
              e.preventDefault();
            }}
            onKeyDown={(e) => {
              handleKeyDown(e, value, "");
              if (blurOnEnter && e.key === "Enter") refInput.current?.blur();
            }}
          />
        </Form.Control>
      ) : (
        <>
          <Input
            id={id}
            ref={refInput}
            type="text"
            onBlur={onInputLostFocus}
            value={value}
            autoFocus={autoFocus}
            disabled={disabled}
            required={required}
            className={classNames(
              password && !pwdVisible && value !== ""
                ? " text-clip password "
                : "",
              editNode ? " input-edit-node " : "",
              password && editNode ? "pr-8" : "",
              password && !editNode ? "pr-10" : "",
              className!
            )}
            placeholder={password && editNode ? "Key" : placeholder}
            onChange={(e) => {
              onChange(e.target.value);
            }}
            onKeyDown={(e) => {
              handleKeyDown(e, value, "");
              if (blurOnEnter && e.key === "Enter") refInput.current?.blur();
            }}
            data-testid={editNode ? id + "-edit" : id}
        />
          <Listbox
            onChange={(val) => {
              onChange(val);
            }}
          >
            <>
              <div className={"relative mt-1 "}>
                <Transition
                  show={showOptions}
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
                      false ? "mb-2 w-[250px]" : "absolute w-full"
                    )}
                  >
                    <div className="flex items-center justify-between px-4 pb-3 pt-2 font-semibold">
                      <div className="flex items-center gap-2">
                        <IconComponent name="Globe" className="h-4 w-4" />
                        Global Variables
                      </div>
                      <div>
                        <AddNewVariableButton>
                          <button className="text-muted-foreground hover:text-accent-foreground">
                            <IconComponent name="Plus" className="h-5 w-5" />
                          </button>
                        </AddNewVariableButton>
                      </div>
                    </div>
                    <Separator />
                    {filteredOptions.map((option, id) => (
                      <Listbox.Option
                        key={id}
                        className={({ active }) =>
                          classNames(
                            active ? " bg-accent" : "",
                            editNode
                              ? "dropdown-component-false-option"
                              : "dropdown-component-true-option",
                            " hover:bg-accent"
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
                                  "dropdown-component-choosal"
                                )}
                              >
                                <IconComponent
                                  name="Check"
                                  className={
                                    "dropdown-component-check-icon text-foreground"
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
          </Listbox>
        </>
      )}

      {options.length > 0 && (
        <span
          className={cn(
            password ? "right-8" : "right-0",
            "absolute inset-y-0 flex items-center pr-2"
          )}
        >
          <button
            onClick={() => {
              setShowOptions(!showOptions);
            }}
            className="text-muted-foreground hover:text-accent-foreground"
          >
            <IconComponent
              name="Globe"
              className="h-4 w-4"
              aria-hidden="true"
            />
          </button>
        </span>
      )}

      {password && (
        <button
          type="button"
          tabIndex={-1}
          className={classNames(
            "mb-px",
            editNode
              ? "input-component-true-button"
              : "input-component-false-button"
          )}
          onClick={(event) => {
            event.preventDefault();
            setPwdVisible(!pwdVisible);
          }}
        >
          {password &&
            (pwdVisible ? (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className={classNames(
                  editNode
                    ? "input-component-true-svg"
                    : "input-component-false-svg"
                )}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"
                />
              </svg>
            ) : (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className={classNames(
                  editNode
                    ? "input-component-true-svg"
                    : "input-component-false-svg"
                )}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            ))}
        </button>
      )}
    </div>
  );
}
