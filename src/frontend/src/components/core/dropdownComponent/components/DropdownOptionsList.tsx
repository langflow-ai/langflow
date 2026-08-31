import type { Dispatch, SetStateAction } from "react";
import NodeDialog from "@/CustomNodes/GenericNode/components/NodeDialogComponent";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import type { APIClassType } from "@/types/api";
import { getStatusColor } from "@/utils/stringManipulation";
import { cn } from "../../../../utils/utils";
import { default as ForwardedIconComponent } from "../../../common/genericIconComponent";
import ShadTooltip from "../../../common/shadTooltipComponent";
import {
  CommandGroup,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "../../../ui/command";
import {
  filterMetadataKeys,
  formatTooltipContent,
} from "../helpers/dropdown-search";

export function DropdownOptionsList({
  filteredOptions,
  filteredMetadata,
  firstWord,
  value,
  onSelect,
  setOpen,
  setWaitingForResponse,
  sourceOptions,
  dialogInputs,
  handleSourceOptions,
  hasRefreshButton,
  handleRefreshButtonPress,
  name,
  openDialog,
  setOpenDialog,
  setPendingSelect,
  nodeId,
  nodeClass,
}: {
  filteredOptions: string[];
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  filteredMetadata: Record<string, any>[] | undefined;
  firstWord: string;
  value: string;
  onSelect: (
    value: string,
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    dbValue?: any,
    skipSnapshot?: boolean,
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    metadata?: any,
  ) => void;
  setOpen: Dispatch<SetStateAction<boolean>>;
  setWaitingForResponse: Dispatch<SetStateAction<boolean>>;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  sourceOptions: any;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  dialogInputs: any;
  handleSourceOptions: (value: string) => void;
  hasRefreshButton?: boolean;
  handleRefreshButtonPress: () => void;
  name?: string;
  openDialog: boolean;
  setOpenDialog: Dispatch<SetStateAction<boolean>>;
  setPendingSelect: Dispatch<SetStateAction<string | null>>;
  nodeId?: string;
  nodeClass?: APIClassType;
}) {
  return (
    <CommandList className="max-h-[300px] overflow-y-auto">
      <CommandGroup defaultChecked={false} className="p-0">
        {filteredOptions?.length > 0 ? (
          filteredOptions?.map((option, index) => (
            <ShadTooltip
              key={index}
              delayDuration={700}
              styleClasses="whitespace-pre-wrap"
              content={formatTooltipContent(
                option,
                index,
                filteredMetadata,
                firstWord,
              )}
            >
              <div>
                <CommandItem
                  value={option}
                  onSelect={(currentValue) => {
                    onSelect(
                      currentValue,
                      undefined,
                      undefined,
                      filteredMetadata?.[index],
                    );
                    setOpen(false);
                    setWaitingForResponse(false);
                  }}
                  className="w-full items-center rounded-none"
                  data-testid={`${option}-${index}-option`}
                >
                  <div
                    className="flex w-full items-center gap-2"
                    data-testid={`dropdown-option-${index}-container`}
                  >
                    {filteredMetadata?.[index]?.icon && (
                      <ForwardedIconComponent
                        name={filteredMetadata?.[index]?.icon || "Unknown"}
                        className="h-4 w-4 shrink-0 text-primary"
                      />
                    )}
                    <div
                      className={cn("flex w-full", {
                        "pl-2": !filteredMetadata?.[index]?.icon,
                      })}
                    >
                      <div className="text-[13px] mr-2 whitespace-nowrap flex-shrink-0">
                        {option}
                      </div>
                      {filteredMetadata?.[index]?.status && (
                        <span
                          className={`flex items-center pl-2 text-xs ${getStatusColor(
                            filteredMetadata?.[index]?.status,
                          )}`}
                        >
                          <LoadingTextComponent
                            text={filteredMetadata?.[
                              index
                            ]?.status?.toLowerCase()}
                          />
                        </span>
                      )}

                      {filteredMetadata && filteredMetadata?.length > 0 && (
                        <div className="ml-auto flex items-center overflow-hidden pl-2 text-muted-foreground">
                          {Object.entries(
                            filterMetadataKeys(filteredMetadata?.[index] || {}),
                          )
                            .filter(
                              ([key, value]) =>
                                value !== null && key !== "icon",
                            )
                            .map(([key, value], i, arr) => (
                              <div
                                key={key}
                                className={cn("flex items-center", {
                                  "flex-1 overflow-hidden":
                                    i === arr.length - 1,
                                })}
                              >
                                {i > 0 && (
                                  <ForwardedIconComponent
                                    name="Circle"
                                    className="mx-1 h-1 w-1 flex-shrink-0 overflow-visible fill-muted-foreground"
                                  />
                                )}
                                <div className="text-xs truncate">
                                  {`${String(value)} ${key}`}
                                </div>
                              </div>
                            ))}
                        </div>
                      )}
                      <div
                        className={cn("pl-2", {
                          "ml-auto":
                            !filteredMetadata || filteredMetadata.length === 0,
                        })}
                      >
                        <ForwardedIconComponent
                          name="Check"
                          className={cn(
                            "h-4 w-4 shrink-0 text-primary",
                            value === option ? "opacity-100" : "opacity-0",
                          )}
                        />
                      </div>
                    </div>
                  </div>
                </CommandItem>
              </div>
            </ShadTooltip>
          ))
        ) : (
          <CommandItem
            disabled
            className="w-full text-center text-sm text-muted-foreground px-2.5 py-1.5"
          >
            No options found
          </CommandItem>
        )}
      </CommandGroup>
      <CommandSeparator />
      {sourceOptions && sourceOptions?.fields && (
        <CommandGroup className="p-0">
          <CommandItem
            className="flex w-full cursor-pointer items-center justify-start gap-2 truncate rounded-none py-2.5 text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
            onSelect={(value) => {
              if (dialogInputs?.fields) {
                setOpenDialog(true);
              } else {
                handleSourceOptions(
                  sourceOptions?.fields?.data?.node?.name! || value,
                );
              }
            }}
          >
            <div className="flex items-center gap-2 pl-1 text-[13px] font-semibold">
              <ForwardedIconComponent name="Plus" className="h-3 w-3 " />
              {sourceOptions?.fields?.data?.node?.display_name}
            </div>
            {sourceOptions?.fields?.data?.node?.icon && (
              <div className="ml-auto">
                <ForwardedIconComponent
                  name={sourceOptions?.fields?.data?.node?.icon}
                  className="h-3 w-3 "
                />
              </div>
            )}
          </CommandItem>

          {hasRefreshButton && (
            <CommandItem
              className="flex w-full cursor-pointer items-center justify-start gap-2 truncate rounded-none py-2.5 text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
              onSelect={() => {
                handleRefreshButtonPress();
              }}
              data-testid={`refresh-dropdown-list-${name}`}
            >
              <div className="flex items-center gap-2 pl-1 text-[13px] font-semibold">
                <ForwardedIconComponent
                  name="RefreshCcw"
                  className={cn("h-3 w-3")}
                />
                Refresh list
              </div>
            </CommandItem>
          )}
          <NodeDialog
            open={openDialog}
            dialogInputs={dialogInputs}
            onClose={() => {
              setOpenDialog(false);
              setOpen(false);
            }}
            onCreated={(createdValue) => {
              setPendingSelect(createdValue);
            }}
            nodeId={nodeId!}
            name={name!}
            nodeClass={nodeClass!}
          />
        </CommandGroup>
      )}
    </CommandList>
  );
}
