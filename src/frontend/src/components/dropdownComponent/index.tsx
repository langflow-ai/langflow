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
}: DropDownComponentType): JSX.Element {
  const [open, setOpen] = useState(false);

  const refButton = useRef<HTMLButtonElement>(null);

  return (
    <>
      {Object.keys(options)?.length > 0 ? (
        <>
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
              <Button
                disabled={disabled}
                variant="primary"
                size="xs"
                role="combobox"
                ref={refButton}
                aria-expanded={open}
                data-test={`${id ?? ""}`}
                className={cn(
                  editNode
                    ? "dropdown-component-outline"
                    : "dropdown-component-false-outline",
                  "w-full justify-between font-normal",
                  editNode ? "input-edit-node" : "py-2"
                )}
              >
                {value &&
                value !== "" &&
                options.find((option) => option === value)
                  ? options.find((option) => option === value)
                  : "Choose an option..."}
                <ForwardedIconComponent
                  name="ChevronsUpDown"
                  className="ml-2 h-4 w-4 shrink-0 opacity-50"
                />
              </Button>
            </PopoverTrigger>
            <PopoverContentWithoutPortal
              className="nocopy nowheel nopan nodelete nodrag noundo w-full p-0"
              style={{ minWidth: refButton?.current?.clientWidth ?? "200px" }}
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
                            value === option ? "opacity-100" : "opacity-0"
                          )}
                        />
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContentWithoutPortal>
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
