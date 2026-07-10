import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useGetTritonModels } from "@/controllers/API/queries/triton/use-get-triton-models";
import {
  useGetTritonRepositoryIndex,
  usePostTritonRepositoryOp,
} from "@/controllers/API/queries/triton/use-post-triton-repository-op";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";

type RepositoryTabProps = {
  serverId: string;
};

export function RepositoryTab({ serverId }: RepositoryTabProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useGetTritonRepositoryIndex({
    serverId,
  });
  const { data: modelsData } = useGetTritonModels({ serverId });
  const { mutateAsync: runOp, isPending } = usePostTritonRepositoryOp();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const modelsStateByName = new Map(
    (modelsData?.models ?? []).map((m) => [m.name, m.state]),
  );

  const handleOp = async (name: string, op: "load" | "unload") => {
    try {
      await runOp({ serverId, modelName: name, op });
      setSuccessData({
        title:
          op === "load"
            ? t("triton.repository.loadSuccess", { name })
            : t("triton.repository.unloadSuccess", { name }),
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorData({ title: t("triton.repository.opError"), list: [msg] });
    }
  };

  if (isLoading) return <Loading />;

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-8">
        <p className="text-sm text-destructive">
          {t("triton.detail.serverUnavailable")}
        </p>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          {t("triton.detail.retry")}
        </Button>
      </div>
    );
  }

  const entries = data ?? [];

  if (entries.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        {t("triton.models.noModels")}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="xs"
          onClick={() => refetch()}
          data-testid="triton-repo-refresh"
        >
          <ForwardedIconComponent name="RefreshCw" className="h-3.5 w-3.5" />
          {t("triton.detail.refresh")}
        </Button>
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("triton.repository.column.name")}</TableHead>
              <TableHead>{t("triton.repository.column.state")}</TableHead>
              <TableHead>{t("triton.repository.column.reason")}</TableHead>
              <TableHead className="text-right">
                {t("triton.repository.column.actions")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => {
              const liveState = modelsStateByName.get(entry.name);
              const isReady = liveState === "READY";
              return (
                <TableRow key={entry.name}>
                  <TableCell className="font-medium">{entry.name}</TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs",
                        isReady
                          ? "bg-accent-emerald text-accent-emerald-foreground"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {liveState ?? entry.state}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {entry.reason || "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="xs"
                      disabled={isPending}
                      onClick={() => handleOp(entry.name, "unload")}
                      data-testid={`triton-repo-unload-${entry.name}`}
                    >
                      <ForwardedIconComponent
                        name="ArrowDownToLine"
                        className="h-3.5 w-3.5"
                      />
                      {t("triton.repository.unload")}
                    </Button>
                    <Button
                      variant="ghost"
                      size="xs"
                      disabled={isPending}
                      onClick={() => handleOp(entry.name, "load")}
                      data-testid={`triton-repo-load-${entry.name}`}
                    >
                      <ForwardedIconComponent
                        name="ArrowUpFromLine"
                        className="h-3.5 w-3.5"
                      />
                      {t("triton.repository.load")}
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
