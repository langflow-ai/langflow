import { useEffect, useMemo, useRef, useState } from "react";
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
  type AvailableKnowledgeBackendId,
  getDefaultKnowledgeBackendConfig,
  getKnowledgeBackendConfig,
  getKnowledgeBackendOption,
  isKnowledgeBackendConfigured,
  KNOWLEDGE_BACKEND_OPTIONS,
  type KnowledgeBackendConfigValue,
  type KnowledgeBackendId,
  type KnowledgeBackendOption,
} from "@/constants/knowledgeBackendConstants";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import type { GlobalVariable } from "@/types/global_variables";
import { cn } from "@/utils/utils";

export type KnowledgeBackendSelection = {
  backend_type: AvailableKnowledgeBackendId;
  backend_config: Record<string, KnowledgeBackendConfigValue>;
};

interface KnowledgeBackendInputProps {
  id: string;
  value: AvailableKnowledgeBackendId;
  globalVariables: GlobalVariable[];
  disabled?: boolean;
  onValueChange: (
    backendType: AvailableKnowledgeBackendId,
    backendConfig: Record<string, KnowledgeBackendConfigValue>,
  ) => void;
}

export default function KnowledgeBackendInputComponent({
  id,
  value,
  disabled,
  handleOnNewValue,
}: BaseInputProps<KnowledgeBackendSelection | AvailableKnowledgeBackendId>) {
  const {
    data: globalVariables = [],
    isFetched,
    isFetching,
  } = useGetGlobalVariables();
  const hasInitializedDefaultRef = useRef(false);

  const currentValue = useMemo(
    () => normalizeKnowledgeBackendValue(value, globalVariables),
    [value, globalVariables],
  );
  const hasBackendValue =
    typeof value === "string" ||
    (typeof value === "object" && Boolean(value?.backend_type));

  useEffect(() => {
    if (hasBackendValue || hasInitializedDefaultRef.current) return;
    if (!isFetched && isFetching) return;
    hasInitializedDefaultRef.current = true;
    handleOnNewValue({ value: currentValue });
  }, [currentValue, handleOnNewValue, hasBackendValue, isFetched, isFetching]);

  return (
    <KnowledgeBackendInput
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

export function KnowledgeBackendInput({
  id,
  value,
  globalVariables,
  disabled,
  onValueChange,
}: KnowledgeBackendInputProps) {
  const navigate = useNavigate();
  const refButton = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

  const selectedBackend = getKnowledgeBackendOption(value);
  const selectedIsConfigured = isKnowledgeBackendConfigured(
    value,
    globalVariables,
  );

  const selectableOptions = useMemo(
    () =>
      KNOWLEDGE_BACKEND_OPTIONS.map((backend) => ({
        backend,
        configured:
          backend.status === "available"
            ? isKnowledgeBackendConfigured(
                backend.id as AvailableKnowledgeBackendId,
                globalVariables,
              )
            : false,
      })),
    [globalVariables],
  );

  const handleSelect = (backend: KnowledgeBackendOption) => {
    if (backend.status !== "available") return;

    const backendType = backend.id as AvailableKnowledgeBackendId;
    if (!isKnowledgeBackendConfigured(backendType, globalVariables)) return;

    onValueChange(
      backendType,
      getKnowledgeBackendConfig(backendType, globalVariables),
    );
    setOpen(false);
  };

  const handleManageBackends = () => {
    setOpen(false);
    navigate("/settings/knowledge-backends");
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
              name={selectedBackend.icon}
              className="h-4 w-4 flex-shrink-0"
            />
            <div className="truncate">
              <div className="flex items-center gap-2 truncate">
                <span className="truncate">{selectedBackend.label}</span>
                {!selectedIsConfigured && (
                  <Badge
                    variant="secondaryStatic"
                    size="sq"
                    className="text-xs"
                  >
                    Needs setup
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
            {selectableOptions.map(({ backend, configured }) => (
              <KnowledgeBackendOptionItem
                key={backend.id}
                backend={backend}
                configured={configured}
                selected={backend.id === value}
                onSelect={() => handleSelect(backend)}
              />
            ))}
          </CommandList>
          <Button
            className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-2 text-xs text-muted-foreground px-3 hover:bg-accent group"
            unstyled
            data-testid="manage-knowledge-backends"
            onClick={handleManageBackends}
          >
            <div className="flex items-center gap-2 pl-1 group-hover:text-primary">
              Manage Knowledge Backends
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

function KnowledgeBackendOptionItem({
  backend,
  configured,
  selected,
  onSelect,
}: {
  backend: KnowledgeBackendOption;
  configured: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const isComingSoon = backend.status === "coming_soon";
  const isDisabled = isComingSoon || !configured;

  return (
    <CommandItem
      value={backend.label}
      disabled={isDisabled}
      onSelect={onSelect}
      className="w-full items-center rounded-none"
      data-testid={`${backend.id}-backend-option`}
    >
      <div className="flex w-full items-center gap-2">
        <ForwardedIconComponent
          name={backend.icon || "Database"}
          className={cn(
            "h-4 w-4 shrink-0 ml-2",
            isDisabled ? "text-muted-foreground" : "text-primary",
          )}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-[13px]">{backend.label}</span>
            {isComingSoon && (
              <Badge variant="secondaryStatic" size="sq" className="text-xs">
                Coming soon
              </Badge>
            )}
            {!isComingSoon && !configured && (
              <Badge variant="secondaryStatic" size="sq" className="text-xs">
                Needs setup
              </Badge>
            )}
          </div>
          <span className="truncate text-[11px] text-muted-foreground">
            {backend.description}
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

function normalizeKnowledgeBackendValue(
  value:
    | KnowledgeBackendSelection
    | AvailableKnowledgeBackendId
    | null
    | undefined,
  globalVariables: GlobalVariable[],
): KnowledgeBackendSelection {
  if (typeof value === "string") {
    const backendType = value === "opensearch" ? "opensearch" : "chroma";
    return {
      backend_type: backendType,
      backend_config: getKnowledgeBackendConfig(backendType, globalVariables),
    };
  }

  if (value?.backend_type) {
    const backendType =
      value.backend_type === "opensearch" ? "opensearch" : "chroma";
    return {
      backend_type: backendType,
      backend_config:
        value.backend_config ??
        getKnowledgeBackendConfig(backendType, globalVariables),
    };
  }

  const defaults = getDefaultKnowledgeBackendConfig(globalVariables);
  return {
    backend_type: defaults.backendType,
    backend_config: defaults.backendConfig,
  };
}

export type BackendValue = AvailableKnowledgeBackendId;
export type KnowledgeBackendValue = KnowledgeBackendId;
