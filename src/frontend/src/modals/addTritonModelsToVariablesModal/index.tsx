import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Loading from "@/components/ui/loading";
import { useGetTritonModels } from "@/controllers/API/queries/triton/use-get-triton-models";
import {
  useGetGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import type { TritonServerType } from "@/types/triton";
import { cn } from "@/utils/utils";

type AddTritonModelsToVariablesModalProps = {
  server: TritonServerType;
  open?: boolean;
  setOpen?: (open: boolean) => void;
};

export default function AddTritonModelsToVariablesModal({
  server,
  open,
  setOpen,
}: AddTritonModelsToVariablesModalProps): JSX.Element {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { data, isLoading, isError, refetch } = useGetTritonModels({
    serverId: server.id,
  });
  const { data: globalVariables } = useGetGlobalVariables();
  const { mutateAsync: addVariable, isPending } = usePostGlobalVariables();

  const [namePrefix, setNamePrefix] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (open) {
      const sanitized = (server.name ?? "")
        .trim()
        .replace(/\s+/g, "_")
        .replace(/[^a-zA-Z0-9_]/g, "");
      setNamePrefix(`triton_${sanitized || "server"}`);
      setSelected(new Set());
    }
  }, [open, server.name]);

  const models = data?.models ?? [];
  const existingNames = useMemo(
    () => new Set((globalVariables ?? []).map((v) => v.name)),
    [globalVariables],
  );

  const generatedNames = useMemo(
    () =>
      models
        .filter((m) => selected.has(m.name))
        .map((m) => `${namePrefix}_${m.name}`),
    [models, selected, namePrefix],
  );

  const conflicting = useMemo(
    () => generatedNames.filter((n) => existingNames.has(n)),
    [generatedNames, existingNames],
  );

  const canSubmit =
    !isPending &&
    selected.size > 0 &&
    namePrefix.trim().length > 0 &&
    conflicting.length === 0;

  const toggleModel = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;
    const chosen = models.filter((m) => selected.has(m.name));
    const results = await Promise.allSettled(
      chosen.map((m) =>
        addVariable({
          name: `${namePrefix}_${m.name}`,
          value: JSON.stringify({
            server_id: server.id,
            ip: server.base_url,
            model: m.name,
          }),
          type: "Generic",
          default_fields: [],
        }),
      ),
    );

    const failed: string[] = [];
    let succeeded = 0;
    results.forEach((r, i) => {
      if (r.status === "fulfilled") succeeded += 1;
      else failed.push(chosen[i].name);
    });

    if (failed.length === 0) {
      setSuccessData({
        title: t("triton.modal.modelsToVarsSuccess", { count: succeeded }),
      });
      setOpen?.(false);
    } else {
      setErrorData({
        title: t("triton.modal.modelsToVarsError"),
        list: [
          t("triton.modal.modelsToVarsPartialError", {
            names: failed.join(", "),
          }),
        ],
      });
    }
  };

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="medium"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description={t("triton.modal.modelsToVarsDescription")}>
        <span className="pr-2">{t("triton.modal.modelsToVarsTitle")}</span>
        <ForwardedIconComponent
          name="Nvidia"
          className="h-5 w-5 text-primary"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4 px-1 pb-2">
          <div className="grid grid-cols-3 gap-2 rounded-md border bg-muted/30 p-3 text-xs">
            <div className="flex flex-col">
              <span className="text-muted-foreground">
                {t("triton.modal.modelsToVarsServerInfo")}
              </span>
              <span className="font-medium">{server.name}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-muted-foreground">IP</span>
              <span className="font-mono break-all">{server.base_url}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-muted-foreground">ID</span>
              <span className="font-mono break-all">{server.id}</span>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="triton-var-prefix">
              {t("triton.modal.modelsToVarsNamePrefix")}
            </Label>
            <Input
              id="triton-var-prefix"
              value={namePrefix}
              onChange={(e) => setNamePrefix(e.target.value)}
              placeholder={t("triton.modal.modelsToVarsNamePrefixPlaceholder")}
              data-testid="triton-var-prefix-input"
            />
            <span className="text-xs text-muted-foreground">
              {t("triton.modal.modelsToVarsNameHint")}
            </span>
          </div>

          <div className="flex flex-col gap-2">
            <Label>{t("triton.modal.modelsToVarsSelectModels")}</Label>
            {isLoading ? (
              <Loading />
            ) : isError ? (
              <div className="flex flex-col items-center gap-2 py-6">
                <span className="text-sm text-destructive">
                  {t("triton.detail.serverUnavailable")}
                </span>
                <button
                  type="button"
                  className="text-sm text-primary underline"
                  onClick={() => refetch()}
                >
                  {t("triton.detail.retry")}
                </button>
              </div>
            ) : models.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {t("triton.modal.modelsToVarsNoModels")}
              </p>
            ) : (
              <div className="flex max-h-64 flex-col gap-1 overflow-auto rounded-md border p-1">
                {models.map((m) => {
                  const checked = selected.has(m.name);
                  const ok = m.state === "READY";
                  return (
                    <label
                      key={m.name}
                      className={cn(
                        "flex cursor-pointer items-center gap-3 rounded px-2 py-1.5 text-sm hover:bg-accent",
                        checked && "bg-accent",
                      )}
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={() => toggleModel(m.name)}
                        data-testid={`triton-model-checkbox-${m.name}`}
                      />
                      <span className="flex-1 font-medium">{m.name}</span>
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
                            ok
                              ? "bg-accent-emerald-foreground"
                              : "bg-muted-foreground",
                          )}
                        />
                        {m.state}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {conflicting.length > 0 && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-2 text-xs text-destructive">
              {t("triton.modal.modelsToVarsConflict", {
                names: conflicting.join(", "),
              })}
            </div>
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("triton.modal.modelsToVarsSubmit"),
          loading: isPending,
          disabled: !canSubmit,
          onClick: handleSubmit,
          dataTestId: "triton-add-vars-btn",
        }}
      />
    </BaseModal>
  );
}
