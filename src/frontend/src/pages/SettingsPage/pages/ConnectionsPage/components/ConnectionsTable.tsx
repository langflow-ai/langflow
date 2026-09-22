import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  ConnectionRead,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections";
import { connectionHandle } from "@/controllers/API/queries/connections";
import { cn } from "@/utils/utils";
import { shortScope } from "../helpers/scopes";
import ConnectionRowMenu, {
  type ConnectionRowMenuProps,
} from "./ConnectionRowMenu";
import ConnectionStatusBadge from "./ConnectionStatusBadge";

export type OwnerKind = "you" | "instance" | "other";

export const ownerKindOf = (
  connection: ConnectionRead,
  currentUserId: string | undefined,
): OwnerKind => {
  if (connection.ownership_mode === "instance") return "instance";
  return connection.owner_id !== null && connection.owner_id === currentUserId
    ? "you"
    : "other";
};

const SORT_COLUMNS = [
  "connection",
  "owner",
  "account",
  "status",
  "scopes",
  "lastCheck",
] as const;
type SortColumn = (typeof SORT_COLUMNS)[number];

export interface ConnectionsSort {
  column: SortColumn;
  direction: "ascending" | "descending";
}

const checkedAt = (iso: string | null): number | null => {
  if (!iso) return null;
  const time = Date.parse(
    /(?:[zZ]|[+-]\d\d:\d\d)$/.test(iso) ? iso : `${iso}Z`,
  );
  return Number.isNaN(time) ? null : time;
};

const HEALTH_DOT: Record<ConnectionRead["health"], string> = {
  healthy: "bg-accent-emerald",
  unhealthy: "bg-error-red",
  unknown: "bg-muted-foreground/50",
};

export interface ConnectionsTableProps {
  connections: ConnectionRead[];
  sort: ConnectionsSort;
  onSortChange: (sort: ConnectionsSort) => void;
  providers: Map<string, IntegrationProviderRead>;
  currentUserId: string | undefined;
  isSuperuser: boolean;
  /** Row currently running a mutation; its menu is disabled while it does. */
  busyId: string | null;
  actions: Omit<
    ConnectionRowMenuProps,
    "connection" | "canAllowUnattended" | "busy"
  >;
}

function ProviderMark({
  providerKey,
  provider,
}: {
  providerKey: string;
  provider: IntegrationProviderRead | undefined;
}) {
  if (provider?.icon) {
    return (
      <ForwardedIconComponent
        name={provider.icon}
        className="h-4 w-4 shrink-0"
        aria-hidden
      />
    );
  }
  return (
    <span
      aria-hidden
      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border bg-muted text-[11px] font-semibold uppercase text-muted-foreground"
    >
      {providerKey.charAt(0)}
    </span>
  );
}

export function ConnectionsTable({
  connections,
  sort,
  onSortChange,
  providers,
  currentUserId,
  isSuperuser,
  busyId,
  actions,
}: ConnectionsTableProps) {
  const { t, i18n } = useTranslation();
  const sortedConnections = useMemo(() => {
    const collator = new Intl.Collator(i18n.language, { numeric: true });
    const sortValue = (connection: ConnectionRead): string | number | null => {
      const account = connection.executing_identity?.account;
      switch (sort.column) {
        case "connection":
          return connection.display_name;
        case "owner":
          return t(
            `connections.owner.${ownerKindOf(connection, currentUserId)}`,
          );
        case "account":
          return account?.display ?? account?.id ?? "";
        case "status":
          return t(`connections.status.${connection.status}`);
        case "scopes":
          return connection.granted_scopes?.length ?? 0;
        case "lastCheck":
          return checkedAt(connection.health_checked_at);
      }
    };
    return [...connections].sort((left, right) => {
      const a = sortValue(left);
      const b = sortValue(right);
      // Never-checked rows stay last in either direction.
      if (a === null && b !== null) return 1;
      if (b === null && a !== null) return -1;
      const comparison =
        typeof a === "number" && typeof b === "number"
          ? a - b
          : collator.compare(String(a ?? ""), String(b ?? ""));
      return (
        comparison * (sort.direction === "ascending" ? 1 : -1) ||
        collator.compare(left.display_name, right.display_name) ||
        left.id.localeCompare(right.id)
      );
    });
  }, [connections, currentUserId, i18n.language, sort, t]);

  const lastChecked = (iso: string | null): string => {
    const then = checkedAt(iso);
    if (then === null) return t("connections.health.never");
    const minutes = Math.max(0, Math.round((Date.now() - then) / 60_000));
    if (minutes < 1) return t("connections.health.justNow");
    if (minutes < 60) return t("connections.health.minutesAgo", { minutes });
    const hours = Math.round(minutes / 60);
    if (hours < 24) return t("connections.health.hoursAgo", { hours });
    return t("connections.health.daysAgo", { days: Math.round(hours / 24) });
  };

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table className="min-w-[880px]">
        <TableHeader>
          <TableRow>
            {SORT_COLUMNS.map((column) => (
              <TableHead
                key={column}
                aria-sort={sort.column === column ? sort.direction : "none"}
              >
                <button
                  type="button"
                  className="flex items-center gap-1 rounded-sm py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  data-testid={`connections-sort-${column}`}
                  onClick={() =>
                    onSortChange({
                      column,
                      direction:
                        sort.column === column && sort.direction === "ascending"
                          ? "descending"
                          : "ascending",
                    })
                  }
                >
                  {t(`connections.columns.${column}`)}
                  <ForwardedIconComponent
                    name={
                      sort.column === column
                        ? sort.direction === "ascending"
                          ? "ArrowUp"
                          : "ArrowDown"
                        : "ArrowUpDown"
                    }
                    className="h-3 w-3 shrink-0"
                    aria-hidden
                  />
                </button>
              </TableHead>
            ))}
            <TableHead className="w-12">
              <span className="sr-only">
                {t("connections.columns.actions")}
              </span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedConnections.map((connection) => {
            const owner = ownerKindOf(connection, currentUserId);
            const account = connection.executing_identity?.account;
            const identity = connection.executing_identity?.identity;
            const scopes = connection.granted_scopes ?? [];

            return (
              <TableRow
                key={connection.id}
                data-testid={`connection-row-${connection.name}`}
                className={cn(busyId === connection.id && "opacity-60")}
              >
                <TableCell>
                  <div className="flex items-center gap-3">
                    <ProviderMark
                      providerKey={connection.provider_key}
                      provider={providers.get(connection.provider_key)}
                    />
                    <div className="flex min-w-0 flex-col">
                      <span className="truncate text-sm font-medium">
                        {connection.display_name}
                      </span>
                      <span className="truncate font-mono text-xs text-muted-foreground">
                        {connectionHandle(connection)}
                      </span>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="text-sm">
                  <ShadTooltip
                    content={
                      owner === "other" && connection.owner_id
                        ? t("connections.owner.id", { id: connection.owner_id })
                        : null
                    }
                  >
                    <span
                      tabIndex={
                        owner === "other" && connection.owner_id ? 0 : undefined
                      }
                    >
                      {t(`connections.owner.${owner}`)}
                    </span>
                  </ShadTooltip>
                </TableCell>
                <TableCell className="text-sm">
                  <div className="flex min-w-0 flex-col">
                    {account ? (
                      <ShadTooltip
                        content={
                          account.tenant_id
                            ? t("connections.account.tenant", {
                                tenant: account.tenant_id,
                              })
                            : null
                        }
                      >
                        <span className="truncate">
                          {account.display ?? account.id}
                        </span>
                      </ShadTooltip>
                    ) : (
                      // Credentials with no account: signed in, but no identity
                      // scope was granted, so the provider named nobody.
                      <span className="text-muted-foreground">
                        {connection.has_credentials
                          ? t("connections.account.unknown")
                          : t("connections.account.notSignedIn")}
                      </span>
                    )}
                    {identity && (
                      <span className="text-xs text-muted-foreground">
                        {t(`connections.identity.${identity}`)}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <ConnectionStatusBadge
                    connection={connection}
                    onAuthorize={actions.onAuthorize}
                  />
                </TableCell>
                <TableCell>
                  {scopes.length === 0 ? (
                    <span className="text-xs text-muted-foreground">
                      {t("connections.scopes.none")}
                    </span>
                  ) : (
                    <ShadTooltip
                      content={
                        <ul className="max-w-xs list-none space-y-0.5 whitespace-normal break-all p-0 font-mono text-xs">
                          {scopes.map((scope) => (
                            <li key={scope}>{scope}</li>
                          ))}
                        </ul>
                      }
                    >
                      <span tabIndex={0}>
                        <Badge variant="secondaryStatic" size="xq">
                          {t("connections.scopes.count", {
                            count: scopes.length,
                          })}
                        </Badge>
                        <span className="sr-only">
                          {scopes.map(shortScope).join(", ")}
                        </span>
                      </span>
                    </ShadTooltip>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2 text-sm">
                    <span
                      aria-hidden
                      className={cn(
                        "h-2 w-2 shrink-0 rounded-full",
                        HEALTH_DOT[connection.health],
                      )}
                    />
                    <span className="sr-only">
                      {t(`connections.health.${connection.health}`)}
                    </span>
                    <span
                      className={cn(
                        connection.health_checked_at
                          ? ""
                          : "text-muted-foreground",
                      )}
                    >
                      {lastChecked(connection.health_checked_at)}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <ConnectionRowMenu
                    connection={connection}
                    canAllowUnattended={
                      owner === "you" || (owner === "instance" && isSuperuser)
                    }
                    busy={busyId === connection.id}
                    {...actions}
                  />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

export default ConnectionsTable;
