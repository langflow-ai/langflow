import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Loading from "@/components/ui/loading";
import { useGetTritonHealth } from "@/controllers/API/queries/triton/use-get-triton-health";
import { useGetTritonServerMeta } from "@/controllers/API/queries/triton/use-get-triton-server-meta";
import { cn } from "@/utils/utils";

type OverviewTabProps = {
  serverId: string;
};

export function OverviewTab({ serverId }: OverviewTabProps) {
  const { t } = useTranslation();
  const live = useGetTritonHealth(
    { serverId, kind: "live" },
    { refetchInterval: 5000 },
  );
  const ready = useGetTritonHealth(
    { serverId, kind: "ready" },
    { refetchInterval: 5000 },
  );
  const meta = useGetTritonServerMeta({ serverId });

  const renderHealth = (
    label: string,
    ok: boolean | undefined,
    loading: boolean,
  ) => (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "h-2.5 w-2.5 rounded-full",
          loading
            ? "bg-muted-foreground/40"
            : ok
              ? "bg-accent-emerald-foreground"
              : "bg-accent-red-foreground",
        )}
      />
      <span className="text-sm">{label}</span>
      <span className="text-xs text-muted-foreground">
        {loading
          ? t("triton.servers.statusLoading")
          : ok
            ? t("triton.servers.statusReady")
            : t("triton.servers.statusDown")}
      </span>
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t("triton.overview.health")}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {renderHealth(
            t("triton.overview.healthLive"),
            live.data?.ok,
            live.isLoading,
          )}
          {renderHealth(
            t("triton.overview.healthReady"),
            ready.data?.ok,
            ready.isLoading,
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t("triton.overview.metadata")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {meta.isLoading ? (
            <Loading />
          ) : meta.isError || !meta.data ? (
            <p className="text-sm text-muted-foreground">
              {t("triton.overview.noMetadata")}
            </p>
          ) : (
            <div className="flex flex-col gap-2 text-sm">
              <Row
                label={t("triton.overview.serverName")}
                value={meta.data.name}
              />
              <Row
                label={t("triton.overview.version")}
                value={meta.data.version}
              />
              <div className="flex flex-col gap-1">
                <span className="text-muted-foreground">
                  {t("triton.overview.extensions")}
                </span>
                <div className="flex flex-wrap gap-1">
                  {(meta.data.extensions ?? []).length === 0 ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : (
                    meta.data.extensions?.map((ext) => (
                      <code
                        key={ext}
                        className="rounded bg-muted px-1.5 py-0.5 text-xs"
                      >
                        {ext}
                      </code>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {(live.isError || ready.isError || meta.isError) && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <ForwardedIconComponent
            name="TriangleAlert"
            className="mt-0.5 h-4 w-4 flex-shrink-0"
          />
          <span>{t("triton.detail.serverUnavailable")}</span>
          <Button
            variant="ghost"
            size="xs"
            className="ml-auto"
            onClick={() => {
              live.refetch();
              ready.refetch();
              meta.refetch();
            }}
          >
            {t("triton.detail.retry")}
          </Button>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-mono text-xs">{value ?? "—"}</span>
    </div>
  );
}
