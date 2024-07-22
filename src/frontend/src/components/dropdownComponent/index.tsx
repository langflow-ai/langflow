import { PopoverAnchor } from "@radix-ui/react-popover";
import { useRef, useState } from "react";
import { DropDownComponentType } from "../../types/components";
import { cn } from "../../utils/utils";
import { default as ForwardedIconComponent } from "../genericIconComponent";
import { Button } from "../ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "../ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "../ui/popover";

export default function Dropdown({
  disabled,
  isLoading,
  value,
  options,
  onSelect,
  editNode = false,
  id = "",
  children,
}: DropDownComponentType): JSX.Element {
  const [open, setOpen] = useState(children ? true : false);

  const refButton = useRef<HTMLButtonElement>(null);

  const PopoverContentDropdown =
    children || editNode ? PopoverContent : PopoverContentWithoutPortal;
  return (
    <>
      {Object.keys(options ?? [])?.length > 0 ? (
        <>
          <Popover open={open} onOpenChange={children ? () => {} : setOpen}>
            {children ? (
              <PopoverAnchor>{children}</PopoverAnchor>
            ) : (
              <PopoverTrigger asChild>
                <Button
                  disabled={disabled}
                  variant="primary"
                  size="xs"
                  role="combobox"
                  ref={refButton}
                  aria-expanded={open}
                  data-testid={`${id ?? ""}`}
                  className={cn(
                    editNode
                      ? "dropdown-component-outline"
                      : "dropdown-component-false-outline",
                    "w-full justify-between font-normal",
                    editNode ? "input-edit-node" : "py-2",
                  )}
                >
                  <span data-testid={`value-dropdown-` + id}>
                    {value &&
                    value !== "" &&
                    options.find((option) => option === value)
                      ? options.find((option) => option === value)
                      : "Choose an option..."}
                  </span>

                  <ForwardedIconComponent
                    name="ChevronsUpDown"
                    className="ml-2 h-4 w-4 shrink-0 opacity-50"
                  />
                </Button>
              </PopoverTrigger>
            )}
            <PopoverContentDropdown
              side="bottom"
              avoidCollisions={!!children}
              className="noflow nowheel nopan nodelete nodrag p-0"
              style={
                children
                  ? {}
                  : { minWidth: refButton?.current?.clientWidth ?? "200px" }
              }
            >
              <Command>
                <CommandInput placeholder="Search options..." className="h-9" />
                <CommandList>
                  <CommandEmpty>No values found.</CommandEmpty>
                  <CommandGroup defaultChecked={false}>
                    {options?.map((option, id) => (
                      <CommandItem
                        key={id}
                        value={option}
                        onSelect={(currentValue) => {
                          onSelect(currentValue);
                          setOpen(false);
                        }}
                        data-testid={`${option}-${id ?? ""}-option`}
                      >
                        {option}
                        <ForwardedIconComponent
                          name="Check"
                          className={cn(
                            "ml-auto h-4 w-4 text-primary",
                            value === option ? "opacity-100" : "opacity-0",
                          )}
                        />
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContentDropdown>
          </Popover>
        </>
      ) : (
        <>
          {(!isLoading && (
            <div>
              <span className="text-sm italic">
                No parameters are available for display.
              </span>
            </div>
          )) || (
            <div>
              <span className="text-sm italic">Loading...</span>
            </div>
          )}
        </>
      )}
    </>
  );
}
