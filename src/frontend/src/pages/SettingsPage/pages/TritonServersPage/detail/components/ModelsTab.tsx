import { useState } from "react";
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
import {
  useGetTritonModelConfig,
  useGetTritonModels,
} from "@/controllers/API/queries/triton/use-get-triton-models";
import { cn } from "@/utils/utils";

type ModelsTabProps = {
  serverId: string;
};

export function ModelsTab({ serverId }: ModelsTabProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useGetTritonModels({
    serverId,
  });
  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) {
    return <Loading />;
  }

  if (isError) {
    return (
      <ErrorState
        onRetry={refetch}
        message={t("triton.detail.serverUnavailable")}
      />
    );
  }

  const models = data?.models ?? [];

  if (models.length === 0) {
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
          data-testid="triton-models-refresh"
        >
          <ForwardedIconComponent name="RefreshCw" className="h-3.5 w-3.5" />
          {t("triton.detail.refresh")}
        </Button>
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("triton.models.column.name")}</TableHead>
              <TableHead>{t("triton.models.column.state")}</TableHead>
              <TableHead>{t("triton.models.column.reason")}</TableHead>
              <TableHead className="text-right">
                {t("triton.models.column.actions")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((m) => (
              <ModelRow
                key={m.name}
                name={m.name}
                state={m.state}
                reason={m.reason}
                expanded={expanded === m.name}
                onToggle={() =>
                  setExpanded(expanded === m.name ? null : m.name)
                }
                serverId={serverId}
              />
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function ModelRow({
  name,
  state,
  reason,
  expanded,
  onToggle,
  serverId,
}: {
  name: string;
  state: string;
  reason?: string;
  expanded: boolean;
  onToggle: () => void;
  serverId: string;
}) {
  const { t } = useTranslation();
  return (
    <>
      <TableRow>
        <TableCell className="font-medium">{name}</TableCell>
        <TableCell>
          <StateBadge state={state} />
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {reason || "—"}
        </TableCell>
        <TableCell className="text-right">
          <Button variant="ghost" size="xs" onClick={onToggle}>
            <ForwardedIconComponent
              name={expanded ? "ChevronUp" : "ChevronDown"}
              className="h-3.5 w-3.5"
            />
            {expanded
              ? t("triton.models.hideConfig")
              : t("triton.models.viewConfig")}
          </Button>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow data-testid={`triton-model-config-${name}`}>
          <TableCell colSpan={4} className="bg-muted/30">
            <ModelConfigView serverId={serverId} modelName={name} />
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function ModelConfigView({
  serverId,
  modelName,
}: {
  serverId: string;
  modelName: string;
}) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useGetTritonModelConfig({
    serverId,
    modelName,
  });

  if (isLoading) return <Loading />;
  if (isError || !data) {
    return (
      <p className="py-2 text-xs text-muted-foreground">
        {t("triton.overview.noMetadata")}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3 p-2 text-sm">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
        <Field
          label={t("triton.models.configPlatform")}
          value={data.platform}
        />
        <Field
          label={t("triton.models.configMaxBatch")}
          value={
            data.max_batch_size?.toString() ??
            data.batcher?.max_batch_size?.toString() ??
            "—"
          }
        />
      </div>
      <TensorList
        title={t("triton.models.configInputs")}
        tensors={data.inputs}
      />
      <TensorList
        title={t("triton.models.configOutputs")}
        tensors={data.outputs}
      />
      {data.parameters && Object.keys(data.parameters).length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            {t("triton.models.configParameters")}
          </p>
          <pre className="overflow-auto rounded bg-muted p-2 text-xs">
            {JSON.stringify(data.parameters, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function TensorList({
  title,
  tensors,
}: {
  title: string;
  tensors?: { name: string; data_type: string; shape: number[] }[];
}) {
  if (!tensors || tensors.length === 0) return null;
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted-foreground">{title}</p>
      <div className="flex flex-col gap-1">
        {tensors.map((tensor) => (
          <div
            key={tensor.name}
            className="flex items-center gap-2 font-mono text-xs"
          >
            <span className="font-medium">{tensor.name}</span>
            <span className="text-muted-foreground">{tensor.data_type}</span>
            <span className="text-muted-foreground">
              [{tensor.shape.join(", ")}]
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-xs">{value ?? "—"}</span>
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  const ok = state === "READY";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs",
        ok
          ? "bg-accent-emerald text-accent-emerald-foreground"
          : "bg-muted text-muted-foreground",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          ok ? "bg-accent-emerald-foreground" : "bg-muted-foreground",
        )}
      />
      {state}
    </span>
  );
}

function ErrorState({
  onRetry,
  message,
}: {
  onRetry: () => void;
  message: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-3 py-8">
      <p className="text-sm text-destructive">{message}</p>
      <Button variant="ghost" size="sm" onClick={onRetry}>
        {t("triton.detail.retry")}
      </Button>
    </div>
  );
}
