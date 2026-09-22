import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Command, CommandItem, CommandList } from "@/components/ui/command";
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useGetConnections } from "@/controllers/API/queries/connections/use-get-connections";
import { activeRequiredScopes } from "@/utils/connection-scopes";
import { cn } from "@/utils/utils";
import type { InputProps } from "../../types";
import {
  focusCommandListOnOpen,
  refocusSelectedCommandItemOnNavigate,
} from "../../utils/focus-command-list-on-open";
import {
  accountLabel,
  buildConnectionOptions,
  type ConnectionOption,
  shortScope,
} from "./helpers/connection-options";
import type { ConnectionRefComponentType } from "./types";

const STATUS_ICON: Record<string, string> = {
  ready: "CircleCheckBig",
  pending: "Clock",
  expired: "CircleAlert",
  revoked: "CircleOff",
  error: "CircleAlert",
};

/**
 * Picker for a `connection_ref` field: selects one managed connection for the
 * component's provider and stores its handle (for example `google/work`) in the
 * flow. The credential itself never reaches the browser; the server resolves
 * the handle to a short-lived credential when the flow runs.
 */
export default function ConnectionRefComponent({
  id,
  value,
  disabled,
  handleOnNewValue,
  placeholder,
  provider,
  requiredScopes = [],
  conditionalScopes,
  inputValues,
  identityKind,
  ariaLabelledBy,
}: InputProps<string, ConnectionRefComponentType>) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const { data, isLoading, isError, isSuccess, isFetching, refetch } =
    useGetConnections({ provider }, { enabled: Boolean(provider) });

  // What the run will ask the resolver to cover: the field's required scopes
  // plus the conditional ones the node's current inputs switch on.
  const scopes = useMemo(
    () =>
      activeRequiredScopes(
        provider,
        requiredScopes,
        conditionalScopes,
        inputValues ?? {},
      ),
    [provider, requiredScopes, conditionalScopes, inputValues],
  );
  const options = useMemo(
    () => buildConnectionOptions(data ?? [], scopes, identityKind),
    [data, scopes, identityKind],
  );
  const selectedHandle = typeof value === "string" ? value : "";
  const selected = options.find((option) => option.handle === selectedHandle);
  // A handle can outlive the connection it names: the flow may come from
  // another workspace, or the connection may have been deleted since. Only a
  // list that loaded can say so; while it loads, or after it failed, a missing
  // match means nothing.
  const isDangling = Boolean(selectedHandle) && isSuccess && !selected;

  const select = (handle: string) => {
    handleOnNewValue({ value: handle });
    setOpen(false);
  };

  const triggerLabel =
    selectedHandle ||
    placeholder ||
    (provider
      ? t("connections.picker.selectProvider", { provider })
      : t("connections.picker.select"));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          ref={triggerRef}
          disabled={disabled}
          variant="primary"
          size="xs"
          role="combobox"
          aria-expanded={open}
          aria-label={!ariaLabelledBy ? triggerLabel : undefined}
          aria-labelledby={ariaLabelledBy}
          data-testid={id}
          className={cn(
            "dropdown-component-false-outline py-2",
            "w-full justify-between font-normal focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          <span className="flex w-full items-center gap-2 overflow-hidden">
            {selected && (
              <ForwardedIconComponent
                name={STATUS_ICON[selected.connection.status] ?? "Plug"}
                className={cn(
                  "h-4 w-4 flex-shrink-0",
                  selected.usable
                    ? "text-accent-emerald-foreground"
                    : "text-destructive",
                )}
              />
            )}
            {isDangling && (
              <ForwardedIconComponent
                name="CircleAlert"
                className="h-4 w-4 flex-shrink-0 text-destructive"
              />
            )}
            <span
              className={cn(
                "truncate",
                !selectedHandle && "text-muted-foreground",
              )}
              data-testid={`value-connection-${id}`}
            >
              {triggerLabel}
            </span>
            {isDangling && (
              <Badge variant="secondaryStatic" size="sq" className="text-xs">
                {t("connections.picker.notFound")}
              </Badge>
            )}
          </span>
          <ForwardedIconComponent
            name={disabled ? "Lock" : "ChevronsUpDown"}
            className="ml-2 h-4 w-4 shrink-0 text-foreground"
          />
        </Button>
      </PopoverTrigger>

      <PopoverContentWithoutPortal
        side="bottom"
        avoidCollisions
        onOpenAutoFocus={focusCommandListOnOpen}
        className="noflow nowheel nopan nodelete nodrag p-0"
        style={{ minWidth: triggerRef.current?.clientWidth ?? "260px" }}
      >
        <Command
          label={t("connections.title")}
          className="flex flex-col"
          onKeyDown={refocusSelectedCommandItemOnNavigate}
        >
          <CommandList className="max-h-[300px] overflow-y-auto">
            {isLoading && (
              <div className="px-3 py-3 text-xs text-muted-foreground">
                {t("connections.loading")}
              </div>
            )}
            {isError && !isLoading && (
              <div className="px-3 py-3 text-xs text-destructive">
                {t("connections.picker.loadFailed")}
              </div>
            )}
            {!isLoading && !isError && options.length === 0 && (
              <div className="px-3 py-3 text-xs text-muted-foreground">
                {provider
                  ? t("connections.picker.emptyProvider", { provider })
                  : t("connections.picker.empty")}
              </div>
            )}
            {options.map((option) => (
              <ConnectionOptionItem
                key={option.handle}
                option={option}
                selected={option.handle === selectedHandle}
                onSelect={() => select(option.handle)}
              />
            ))}
          </CommandList>
        </Command>

        <div className="flex items-center justify-between gap-2 border-t border-border bg-background px-3 py-2">
          <span className="truncate text-[11px] text-muted-foreground">
            {scopes.length
              ? t("connections.picker.requires", {
                  scopes: scopes.map(shortScope).join(", "),
                })
              : t("connections.picker.noScopes")}
          </span>
          <div className="flex items-center gap-1">
            {selectedHandle && (
              <Button
                unstyled
                className="px-1 text-xs text-muted-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring"
                data-testid={`clear-connection-${id}`}
                onClick={() => select("")}
              >
                {t("connections.picker.clear")}
              </Button>
            )}
            <Button
              unstyled
              className="flex items-center gap-1 px-1 text-xs text-muted-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring"
              data-testid={`refresh-connections-${id}`}
              onClick={() => refetch()}
            >
              <ForwardedIconComponent
                name="RefreshCcw"
                className={cn("h-3 w-3", isFetching && "animate-spin")}
              />
              {t("connections.picker.refresh")}
            </Button>
          </div>
        </div>
      </PopoverContentWithoutPortal>
    </Popover>
  );
}

function ConnectionOptionItem({
  option,
  selected,
  onSelect,
}: {
  option: ConnectionOption;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  const { connection, usable, unusableReason } = option;
  const reason =
    unusableReason === "status"
      ? t(`connections.status.${connection.status}`)
      : unusableReason === "scopes"
        ? t("connections.picker.missingScopes", {
            scopes: option.missingScopes.map(shortScope).join(", "),
          })
        : unusableReason
          ? t(`connections.picker.${unusableReason}`)
          : undefined;
  return (
    <CommandItem
      value={option.handle}
      // An unusable connection stays selectable: the run then fails with a
      // typed error that names the fix, which beats an inert row.
      onSelect={onSelect}
      className="w-full items-center rounded-none"
      data-testid={`connection-option-${option.handle}`}
    >
      <div className="flex w-full items-center gap-2">
        <ForwardedIconComponent
          name={STATUS_ICON[connection.status] ?? "Plug"}
          className={cn(
            "ml-2 h-4 w-4 shrink-0",
            usable ? "text-accent-emerald-foreground" : "text-muted-foreground",
          )}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate font-mono text-[13px]">
              {option.handle}
            </span>
            {!usable && (
              <Badge variant="secondaryStatic" size="sq" className="text-xs">
                {reason}
              </Badge>
            )}
          </div>
          <span className="truncate text-[11px] text-muted-foreground">
            {accountLabel(connection)}
          </span>
        </div>
        {selected && (
          <ForwardedIconComponent
            name="Check"
            className="mr-2 h-4 w-4 shrink-0 text-primary"
          />
        )}
      </div>
    </CommandItem>
  );
}
