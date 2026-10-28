import { useTranslation } from "react-i18next";
import type { TriggerStateFilter } from "@/components/core/triggers/helpers/filter-triggers";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const STATE_FILTERS: TriggerStateFilter[] = [
  "all",
  "attention",
  "pending",
  "active",
  "paused",
  "expired",
  "needs_reconnect",
  "error",
];

export interface TriggersToolbarProps {
  search: string;
  onSearchChange: (search: string) => void;
  state: TriggerStateFilter;
  onStateChange: (state: TriggerStateFilter) => void;
  attentionCount: number;
  /** Operator view: filter by provider. */
  providers?: string[];
  provider?: string;
  onProviderChange?: (provider: string | undefined) => void;
  searchPlaceholderKey: string;
}

const ALL_PROVIDERS = "__all__";

export function TriggersToolbar({
  search,
  onSearchChange,
  state,
  onStateChange,
  attentionCount,
  providers,
  provider,
  onProviderChange,
  searchPlaceholderKey,
}: TriggersToolbarProps) {
  const { t } = useTranslation();
  const attentionOn = state === "attention";
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Input
        type="search"
        placeholder={t(searchPlaceholderKey)}
        aria-label={t(searchPlaceholderKey)}
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        icon="Search"
        className="w-72 shrink-0"
        data-testid="triggers-search"
      />
      {providers && onProviderChange && (
        <Select
          value={provider ?? ALL_PROVIDERS}
          onValueChange={(value) =>
            onProviderChange(value === ALL_PROVIDERS ? undefined : value)
          }
        >
          <SelectTrigger
            className="w-44"
            aria-label={t("triggers.filters.provider")}
            data-testid="triggers-provider-filter"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_PROVIDERS}>
              {t("triggers.filters.allProviders")}
            </SelectItem>
            {providers.map((id) => (
              <SelectItem key={id} value={id}>
                {t(`triggers.provider.${id}`, { defaultValue: id })}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      <Select
        value={state}
        onValueChange={(value) => onStateChange(value as TriggerStateFilter)}
      >
        <SelectTrigger
          className="w-48"
          aria-label={t("triggers.filters.state")}
          data-testid="triggers-state-filter"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {STATE_FILTERS.map((filter) => (
            <SelectItem key={filter} value={filter}>
              {t(`triggers.filters.states.${filter}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {attentionCount > 0 && (
        <button
          type="button"
          aria-pressed={attentionOn}
          onClick={() => onStateChange(attentionOn ? "all" : "attention")}
          className="flex h-9 items-center gap-2 rounded-md border px-3 text-sm hover:bg-muted aria-pressed:bg-muted"
          data-testid="triggers-attention-toggle"
        >
          <span
            aria-hidden="true"
            className="h-2 w-2 rounded-full bg-accent-amber-foreground"
          />
          {t("triggers.filters.attention", { count: attentionCount })}
        </button>
      )}
    </div>
  );
}

export default TriggersToolbar;
