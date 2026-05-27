import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { BaseInputProps } from "@/components/core/parameterRenderComponent/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Command, CommandItem, CommandList } from "@/components/ui/command";
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  type AvailableDBProviderId,
  DB_PROVIDER_OPTIONS,
  type DBProviderConfigValue,
  type DBProviderId,
  type DBProviderOption,
  getDBProviderConfig,
  getDBProviderOption,
  getDefaultDBProviderConfig,
  isDBProviderConfigured,
  resolveUIBackendType,
} from "@/constants/dbProviderConstants";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import type { GlobalVariable } from "@/types/global_variables";
import { cn } from "@/utils/utils";

export type DBProviderSelection = {
  // Wire keys stay snake_case to match the backend payload format.
  backend_type: AvailableDBProviderId;
  backend_config: Record<string, DBProviderConfigValue>;
};

interface DBProviderInputProps {
  id: string;
  value: AvailableDBProviderId;
  globalVariables: GlobalVariable[];
  disabled?: boolean;
  onValueChange: (
    backendType: AvailableDBProviderId,
    backendConfig: Record<string, DBProviderConfigValue>,
  ) => void;
}

export default function DBProviderInputComponent({
  id,
  value,
  disabled,
  handleOnNewValue,
}: BaseInputProps<DBProviderSelection | AvailableDBProviderId>) {
  const {
    data: globalVariables = [],
    isFetched,
    isFetching,
  } = useGetGlobalVariables();
  const hasInitializedDefaultRef = useRef(false);

  const currentValue = useMemo(
    () => normalizeDBProviderValue(value, globalVariables),
    [value, globalVariables],
  );
  const hasProviderValue =
    typeof value === "string" ||
    (typeof value === "object" && Boolean(value?.backend_type));

  useEffect(() => {
    if (hasProviderValue || hasInitializedDefaultRef.current) return;
    if (!isFetched && isFetching) return;
    hasInitializedDefaultRef.current = true;
    handleOnNewValue({ value: currentValue });
  }, [currentValue, handleOnNewValue, hasProviderValue, isFetched, isFetching]);

  return (
    <DBProviderInput
      id={id}
      value={currentValue.backend_type}
      globalVariables={globalVariables}
      disabled={disabled}
      onValueChange={(backendType, backendConfig) => {
        handleOnNewValue({
          value: {
            backend_type: backendType,
            backend_config: backendConfig,
          },
        });
      }}
    />
  );
}

export function DBProviderInput({
  id,
  value,
  globalVariables,
  disabled,
  onValueChange,
}: DBProviderInputProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const refButton = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

  const selectedProvider = getDBProviderOption(value);
  const selectedIsConfigured = isDBProviderConfigured(value, globalVariables);

  const selectableOptions = useMemo(
    () =>
      DB_PROVIDER_OPTIONS.map((provider) => ({
        provider,
        configured:
          provider.status === "available"
            ? isDBProviderConfigured(
                provider.id as AvailableDBProviderId,
                globalVariables,
              )
            : false,
      })),
    [globalVariables],
  );

  const handleSelect = (provider: DBProviderOption) => {
    if (provider.status !== "available") return;

    const backendType = provider.id as AvailableDBProviderId;
    if (!isDBProviderConfigured(backendType, globalVariables)) return;

    onValueChange(
      backendType,
      getDBProviderConfig(backendType, globalVariables),
    );
    setOpen(false);
  };

  const handleManageProviders = () => {
    setOpen(false);
    navigate("/settings/db-providers");
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          disabled={disabled}
          variant="primary"
          size="xs"
          role="combobox"
          ref={refButton}
          aria-expanded={open}
          data-testid={id}
          className={cn(
            "dropdown-component-false-outline py-2",
            "no-focus-visible w-full justify-between font-normal disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          <span
            className="flex w-full items-center gap-2 overflow-hidden"
            data-testid={`value-dropdown-${id}`}
          >
            <ForwardedIconComponent
              name={selectedProvider.icon}
              className="h-4 w-4 flex-shrink-0"
            />
            <div className="truncate">
              <div className="flex items-center gap-2 truncate">
                <span className="truncate">{selectedProvider.label}</span>
                {!selectedIsConfigured && (
                  <Badge
                    variant="secondaryStatic"
                    size="sq"
                    className="text-xs"
                  >
                    {t("settings.dbProviders.needsSetup")}
                  </Badge>
                )}
              </div>
            </div>
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
      <PopoverContentWithoutPortal
        side="bottom"
        avoidCollisions={true}
        className="noflow nowheel nopan nodelete nodrag p-0"
        style={{ minWidth: refButton?.current?.clientWidth ?? "240px" }}
      >
        <Command className="flex flex-col">
          <CommandList className="max-h-[300px] overflow-y-auto">
            {selectableOptions.map(({ provider, configured }) => (
              <DBProviderOptionItem
                key={provider.id}
                provider={provider}
                configured={configured}
                selected={provider.id === value}
                onSelect={() => handleSelect(provider)}
              />
            ))}
          </CommandList>
          <Button
            className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-2 text-xs text-muted-foreground px-3 hover:bg-accent group"
            unstyled
            data-testid="manage-db-providers"
            onClick={handleManageProviders}
          >
            <div className="flex items-center gap-2 pl-1 group-hover:text-primary">
              {t("settings.dbProviders.manage")}
              <ForwardedIconComponent
                name="Settings"
                className="w-4 h-4 text-muted-foreground group-hover:text-primary"
              />
            </div>
          </Button>
        </Command>
      </PopoverContentWithoutPortal>
    </Popover>
  );
}

function DBProviderOptionItem({
  provider,
  configured,
  selected,
  onSelect,
}: {
  provider: DBProviderOption;
  configured: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  const isComingSoon = provider.status === "coming_soon";
  const isDisabled = isComingSoon || !configured;

  return (
    <CommandItem
      value={provider.label}
      disabled={isDisabled}
      onSelect={onSelect}
      className="w-full items-center rounded-none"
      data-testid={`${provider.id}-provider-option`}
    >
      <div className="flex w-full items-center gap-2">
        <ForwardedIconComponent
          name={provider.icon || "Database"}
          className={cn(
            "h-4 w-4 shrink-0 ml-2",
            isDisabled ? "text-muted-foreground" : "text-primary",
          )}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-[13px]">{provider.label}</span>
            {isComingSoon && (
              <Badge variant="secondaryStatic" size="sq" className="text-xs">
                {t("settings.dbProviders.comingSoon")}
              </Badge>
            )}
            {!isComingSoon && !configured && (
              <Badge variant="secondaryStatic" size="sq" className="text-xs">
                {t("settings.dbProviders.needsSetup")}
              </Badge>
            )}
          </div>
          <span className="truncate text-[11px] text-muted-foreground">
            {provider.description}
          </span>
        </div>
        <ForwardedIconComponent
          name="Check"
          className={cn(
            "h-4 w-4 shrink-0 text-primary",
            selected ? "opacity-100" : "opacity-0",
          )}
        />
      </div>
    </CommandItem>
  );
}

function normalizeDBProviderValue(
  value: DBProviderSelection | AvailableDBProviderId | null | undefined,
  globalVariables: GlobalVariable[],
): DBProviderSelection {
  if (typeof value === "string") {
    const backendType: AvailableDBProviderId =
      value === "opensearch"
        ? "opensearch"
        : value === "chroma_cloud"
          ? "chroma_cloud"
          : "chroma";
    return {
      backend_type: backendType,
      backend_config: getDBProviderConfig(backendType, globalVariables),
    };
  }

  if (value?.backend_type) {
    const backendType = resolveUIBackendType(
      value.backend_type,
      value.backend_config as Record<string, unknown> | undefined,
    );
    return {
      backend_type: backendType,
      backend_config:
        value.backend_config ??
        getDBProviderConfig(backendType, globalVariables),
    };
  }

  const defaults = getDefaultDBProviderConfig(globalVariables);
  return {
    backend_type: defaults.backendType,
    backend_config: defaults.backendConfig,
  };
}

export type ProviderValue = AvailableDBProviderId;
export type DBProviderValue = DBProviderId;
