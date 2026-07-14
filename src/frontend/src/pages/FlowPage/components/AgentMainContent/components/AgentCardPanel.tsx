import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import InputListComponent from "@/components/core/parameterRenderComponent/components/inputListComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs-button";
import { Textarea } from "@/components/ui/textarea";
import {
  type A2ACardForm,
  formToOverrides,
  overridesToForm,
} from "@/controllers/API/queries/a2a/utils";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { cn } from "@/utils/utils";
import {
  type A2AAgentCard,
  cardInputContract,
  cardRequiresApiKey,
} from "../types";

const errorDetail = (e: unknown, fallback: string): string => {
  const err = e as {
    response?: { data?: { detail?: string } };
    message?: string;
  };
  return err.response?.data?.detail || err.message || fallback;
};

const curlSnippet = (rpcUrl: string, requiresApiKey: boolean): string => {
  const key = requiresApiKey ? " \\\n  -H 'x-api-key: <YOUR_API_KEY>'" : "";
  return `curl -X POST '${rpcUrl}' \\
  -H 'Content-Type: application/json'${key} \\
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Hello"}],"messageId":"1"}}}'`;
};

export default function AgentCardPanel({
  currentFlow,
  serverEnabled,
  eligible,
  hasInput,
  hasOutput,
  card,
  cardLoading,
}: {
  currentFlow?: FlowType | null;
  serverEnabled: boolean;
  eligible: boolean;
  hasInput: boolean;
  hasOutput: boolean;
  card: A2AAgentCard | null;
  cardLoading: boolean;
}) {
  const { t } = useTranslation();
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync, isPending } = usePatchUpdateFlow();

  const flowId = currentFlow?.id ?? "";
  const isPublished = !!currentFlow?.a2a_enabled;
  const cardUrl = `${window.location.origin}/api/v1/a2a/${flowId}/.well-known/agent-card.json`;
  const rpcUrl = `${window.location.origin}/api/v1/a2a/${flowId}/jsonrpc`;

  const [enabled, setEnabled] = useState(isPublished);
  const [form, setForm] = useState<A2ACardForm>(
    overridesToForm(currentFlow?.a2a_card_overrides),
  );

  // Re-seed only when the persisted A2A state changes, so unrelated flow updates
  // (graph edits, autosave) don't clobber in-progress card edits.
  useEffect(() => {
    setEnabled(!!currentFlow?.a2a_enabled);
    setForm(overridesToForm(currentFlow?.a2a_card_overrides));
  }, [currentFlow?.a2a_enabled, currentFlow?.a2a_card_overrides]);

  const savedForm = overridesToForm(currentFlow?.a2a_card_overrides);
  const isDirty =
    enabled !== isPublished ||
    JSON.stringify(form) !== JSON.stringify(savedForm);

  const setField = (field: "name" | "description" | "version", value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));
  const setList = (field: "tags" | "examples", value: string[]) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSave = async () => {
    try {
      const updatedFlow = await mutateAsync({
        id: flowId,
        // flow_type is derived from the graph (has chat I/O = agent). Write it
        // here so the langflow A2A serve guard passes; an ineligible flow can
        // never be served, so force it off. (Backend derive-on-save is a
        // follow-up; today the tab is the only place that recomputes it.)
        flow_type: eligible ? "agent" : "workflow",
        a2a_enabled: eligible ? enabled : false,
        a2a_card_overrides: formToOverrides(form),
      });
      if (flows) {
        setFlows(flows.map((f) => (f.id === updatedFlow.id ? updatedFlow : f)));
      }
      setCurrentFlow(updatedFlow);
      setSuccessData({ title: t("agentTab.saved") });
    } catch (e) {
      setErrorData({
        title: t("agentTab.saveError"),
        list: [errorDetail(e, "Unknown error")],
      });
    }
  };

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setSuccessData({ title: t("agentTab.copied") });
    } catch {
      setErrorData({ title: t("agentTab.copyError") });
    }
  };

  const contract = useMemo(() => cardInputContract(card), [card]);
  const requiresApiKey = cardRequiresApiKey(card);

  // Resolved identity: the live card wins once published; otherwise fall back to
  // the local overrides + flow so the draft still shows what will be published.
  const displayName = card?.name || form.name || currentFlow?.name || "";
  const displayVersion = card?.version || form.version || "";
  const displayDescription =
    card?.description || form.description || currentFlow?.description || "";

  const status = !serverEnabled
    ? { label: t("agentTab.statusOff"), variant: "secondaryStatic" as const }
    : !eligible
      ? {
          label: t("agentTab.statusUnavailable"),
          variant: "secondaryStatic" as const,
        }
      : isPublished
        ? { label: t("agentTab.statusLive"), variant: "successStatic" as const }
        : {
            label: t("agentTab.statusDraft"),
            variant: "secondaryStatic" as const,
          };

  // What to tell the user when the flow can't serve: the server switch wins,
  // then eligibility (a published flow that lost its chat I/O needs turning
  // off; a draft one just needs the missing half added).
  const banner = !serverEnabled
    ? t("agentTab.serverDisabled")
    : !eligible
      ? isPublished
        ? t("agentTab.ineligibleServing")
        : !hasInput && !hasOutput
          ? t("agentTab.ineligible")
          : !hasInput
            ? t("agentTab.ineligibleNoInput")
            : t("agentTab.ineligibleNoOutput")
      : null;

  return (
    <div className="flex flex-col gap-6">
      {banner && (
        <div className="flex items-center gap-2 rounded-md bg-accent-amber/10 p-2 text-mmd text-accent-amber-foreground">
          <ForwardedIconComponent
            name="AlertTriangle"
            className="h-4 w-4 shrink-0"
          />
          {banner}
        </div>
      )}

      {/* Publish */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium">
            {t("agentTab.publishLabel")}
          </span>
          <span className="text-mmd text-muted-foreground">
            {!eligible
              ? t("agentTab.publishIneligible")
              : isPublished
                ? t("agentTab.publishLive")
                : enabled
                  ? t("agentTab.publishPending")
                  : t("agentTab.publishOff")}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={status.variant} size="sm" data-testid="agent-status">
            {status.label}
          </Badge>
          <Switch
            data-testid="agent-publish-switch"
            checked={enabled}
            // Block turning ON an ineligible flow, but leave it operable when
            // it's already serving so the user can honestly turn it off.
            disabled={!serverEnabled || (!eligible && !enabled)}
            onCheckedChange={setEnabled}
          />
        </div>
      </div>

      {/* Agent card preview */}
      <div className="flex flex-col gap-3 rounded-lg border bg-muted/40 p-4">
        <div className="flex items-baseline justify-between gap-2">
          <span
            className="text-base font-semibold"
            data-testid="agent-card-name"
          >
            {displayName || t("agentTab.untitled")}
          </span>
          <span className="shrink-0 text-mmd text-muted-foreground">
            {[displayVersion, t("agentTab.fromThisFlow")]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </div>
        {displayDescription && (
          <p className="text-mmd text-muted-foreground">{displayDescription}</p>
        )}

        <div className="flex items-center gap-1.5 text-mmd text-muted-foreground">
          <ForwardedIconComponent
            name={requiresApiKey ? "KeyRound" : "Globe"}
            className="h-3.5 w-3.5 shrink-0"
          />
          {isPublished
            ? requiresApiKey
              ? t("agentTab.exposureRestricted")
              : t("agentTab.exposurePublic")
            : t("agentTab.exposureDraft")}
        </div>

        {/* Input contract — only exists once the card is served */}
        {isPublished ? (
          <div className="flex flex-col gap-2 border-t pt-3">
            <div className="flex items-baseline gap-2">
              <span className="text-mmd font-medium">
                {t("agentTab.inputContract")}
              </span>
              <span className="text-xs text-muted-foreground">
                {t("agentTab.inputContractHint")}
              </span>
            </div>
            {cardLoading && contract.length === 0 ? (
              <span className="text-mmd text-muted-foreground">…</span>
            ) : contract.length === 0 ? (
              <span className="text-mmd text-muted-foreground">
                {t("agentTab.inputContractEmpty")}
              </span>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {contract.map((field) => (
                  <li
                    key={field.name}
                    className="flex items-baseline gap-2 text-mmd"
                  >
                    <code className="rounded bg-muted px-1 font-medium">
                      {field.name}
                    </code>
                    <span className="text-muted-foreground">{field.type}</span>
                    <span
                      className={cn(
                        "text-xs",
                        field.required
                          ? "text-accent-amber-foreground"
                          : "text-muted-foreground",
                      )}
                    >
                      {field.required
                        ? t("agentTab.required")
                        : t("agentTab.optional")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="border-t pt-3 text-mmd text-muted-foreground">
            {t("agentTab.draftContractNote")}
          </div>
        )}
      </div>

      {/* Address + copy-as */}
      <div className="flex flex-col gap-2">
        <Label className="text-mmd font-medium">
          {t("agentTab.addressLabel")}
        </Label>
        <Tabs defaultValue="url">
          <TabsList>
            <TabsTrigger value="url">{t("agentTab.copyUrl")}</TabsTrigger>
            <TabsTrigger value="curl">{t("agentTab.copyCurl")}</TabsTrigger>
          </TabsList>
          <TabsContent value="url" className="mt-2">
            <div className="flex items-center gap-2">
              <Input readOnly value={cardUrl} data-testid="agent-card-url" />
              <Button
                variant="outline"
                size="icon"
                aria-label={t("agentTab.copyUrlAria")}
                onClick={() => copy(cardUrl)}
              >
                <ForwardedIconComponent name="Copy" className="h-4 w-4" />
              </Button>
            </div>
          </TabsContent>
          <TabsContent value="curl" className="mt-2">
            <div className="flex items-start gap-2">
              <pre className="flex-1 overflow-x-auto rounded-md bg-muted p-3 text-xs">
                {curlSnippet(rpcUrl, requiresApiKey)}
              </pre>
              <Button
                variant="outline"
                size="icon"
                aria-label={t("agentTab.copyCurlAria")}
                onClick={() => copy(curlSnippet(rpcUrl, requiresApiKey))}
              >
                <ForwardedIconComponent name="Copy" className="h-4 w-4" />
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Customize card */}
      <div className="flex flex-col gap-3 border-t pt-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-mmd font-medium">
            {t("agentTab.customizeTitle")}
          </span>
          <span className="text-xs text-muted-foreground">
            {t("agentTab.customizeHint")}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label className="text-mmd font-medium">
              {t("agentTab.nameLabel")}
            </Label>
            <Input
              placeholder={currentFlow?.name ?? ""}
              value={form.name}
              onChange={(e) => setField("name", e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-mmd font-medium">
              {t("agentTab.versionLabel")}
            </Label>
            <Input
              value={form.version}
              onChange={(e) => setField("version", e.target.value)}
            />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className="text-mmd font-medium">
            {t("agentTab.descriptionLabel")}
          </Label>
          <Textarea
            className="min-h-16"
            placeholder={currentFlow?.description ?? ""}
            value={form.description}
            onChange={(e) => setField("description", e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className="text-mmd font-medium">
            {t("agentTab.tagsLabel")}
          </Label>
          <span className="text-xs text-muted-foreground">
            {t("agentTab.tagsHint")}
          </span>
          <InputListComponent
            id="agent-tags"
            editNode={false}
            disabled={false}
            value={form.tags.length ? form.tags : [""]}
            handleOnNewValue={({ value }) =>
              setList("tags", (value ?? []) as string[])
            }
            placeholder={t("agentTab.tagPlaceholder")}
            listAddLabel={t("agentTab.addTag")}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className="text-mmd font-medium">
            {t("agentTab.examplesLabel")}
          </Label>
          <span className="text-xs text-muted-foreground">
            {t("agentTab.examplesHint")}
          </span>
          <InputListComponent
            id="agent-examples"
            editNode={false}
            disabled={false}
            value={form.examples.length ? form.examples : [""]}
            handleOnNewValue={({ value }) =>
              setList("examples", (value ?? []) as string[])
            }
            placeholder={t("agentTab.examplePlaceholder")}
            listAddLabel={t("agentTab.addExample")}
          />
        </div>
      </div>

      <Button
        className="w-full"
        onClick={handleSave}
        loading={isPending}
        disabled={!isDirty}
        data-testid="agent-save"
      >
        {t("agentTab.save")}
      </Button>
    </div>
  );
}
