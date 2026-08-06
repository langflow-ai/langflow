import type { RefObject } from "react";
import { useTranslation } from "react-i18next";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { convertStringToHTML } from "@/utils/stringManipulation";
import { cn } from "../../../../utils/utils";
import { default as ForwardedIconComponent } from "../../../common/genericIconComponent";
import { Button } from "../../../ui/button";
import { PopoverTrigger } from "../../../ui/popover";

export function DropdownTrigger({
  disabled,
  validOptions,
  combobox,
  sourceOptions,
  hasRefreshButton,
  editNode,
  open,
  refButton,
  id,
  value,
  options,
  placeholder,
  helperText,
  filteredOptions,
  filteredMetadata,
}: {
  disabled?: boolean;
  validOptions: string[];
  combobox?: boolean;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  sourceOptions: any;
  hasRefreshButton?: boolean;
  editNode?: boolean;
  open: boolean;
  refButton: RefObject<HTMLButtonElement | null>;
  id: string;
  value: string;
  options?: string[];
  placeholder?: string;
  helperText?: string;
  filteredOptions: string[];
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  filteredMetadata: Record<string, any>[] | undefined;
}) {
  const { t } = useTranslation();

  const renderSelectedIcon = () => {
    const selectedIndex = filteredOptions.findIndex(
      (option) => option === value,
    );
    const iconMetadata =
      selectedIndex >= 0 ? filteredMetadata?.[selectedIndex]?.icon : undefined;

    return iconMetadata ? (
      <ForwardedIconComponent
        name={iconMetadata}
        className="h-4 w-4 flex-shrink-0"
      />
    ) : null;
  };

  return (
    <div className="flex w-full flex-col">
      <PopoverTrigger asChild>
        <Button
          disabled={
            disabled ||
            (Object.keys(validOptions).length === 0 &&
              !combobox &&
              !sourceOptions?.fields?.data?.node?.template &&
              !hasRefreshButton &&
              !sourceOptions?.fields)
          }
          variant="primary"
          size="xs"
          role="combobox"
          ref={refButton}
          aria-expanded={open}
          data-testid={id}
          className={cn(
            editNode
              ? "dropdown-component-outline input-edit-node"
              : "dropdown-component-false-outline py-2",
            "focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 w-full justify-between font-normal disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          <span
            className="flex w-full items-center gap-2 overflow-hidden"
            data-testid={`value-dropdown-${id}`}
          >
            {value && <>{renderSelectedIcon()}</>}
            <span className="truncate">
              {disabled ? (
                t("component.receivingInput")
              ) : (
                <>
                  {
                    options?.includes(value) ? (
                      value
                    ) : // this logic is used for the agents component, if you update make sure to test the agent component
                    sourceOptions?.fields?.data?.node?.name ===
                      "connect_other_models" ? (
                      <span className="text-muted-foreground">
                        <LoadingTextComponent
                          text={placeholder || t("component.selectOption")}
                        />
                      </span>
                    ) : (
                      placeholder || t("component.selectOption")
                    )
                    // ) : (
                    //   <span className="text-muted-foreground">
                    //     <LoadingTextComponent
                    //       text={placeholder || t("component.selectOption")}
                    //     />
                    //   </span>
                    // )}
                  }
                </>
              )}
            </span>
          </span>

          <ForwardedIconComponent
            name={disabled ? "Lock" : "ChevronsUpDown"}
            className={cn(
              "ml-2 h-4 w-4 shrink-0 text-foreground",
              disabled
                ? "text-placeholder-foreground hover:text-placeholder-foreground"
                : "hover:text-foreground",
            )}
          />
        </Button>
      </PopoverTrigger>
      {helperText && (
        <span className="pt-2 text-xs text-muted-foreground">
          {convertStringToHTML(helperText)}
        </span>
      )}
    </div>
  );
}
