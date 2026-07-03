import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { usePostA2AMessage } from "@/controllers/API/queries/a2a/use-post-a2a-message";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";
import BaseModal from "../baseModal";
import {
  type A2ACardForm,
  formToOverrides,
  overridesToForm,
  parseA2AReply,
} from "./utils";

const errorDetail = (e: unknown, fallback: string): string => {
  const err = e as {
    response?: { data?: { detail?: string } };
    message?: string;
  };
  return err.response?.data?.detail || err.message || fallback;
};

export default function A2AModal({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  // Server-wide A2A flag (LANGFLOW_A2A_ENABLED). When off, the whole A2A surface 404s, so
  // explain that here rather than letting publish/test hit a dead endpoint.
  const serverA2aEnabled = useUtilityStore((state) => state.a2aEnabled);
  const { mutateAsync, isPending } = usePatchUpdateFlow();
  const { mutateAsync: sendMessage, isPending: isSending } =
    usePostA2AMessage();

  const flowId = currentFlow?.id ?? "";
  const isAgent = currentFlow?.flow_type === "agent";
  const cardUrl = `${window.location.origin}/api/v1/a2a/${flowId}/.well-known/agent-card.json`;

  const [enabled, setEnabled] = useState(!!currentFlow?.a2a_enabled);
  const [form, setForm] = useState<A2ACardForm>(
    overridesToForm(currentFlow?.a2a_card_overrides),
  );
  const [testInput, setTestInput] = useState("");
  const [testReply, setTestReply] = useState("");
  const [testFailed, setTestFailed] = useState(false);

  // The live endpoint only serves once publishing is SAVED, so testing gates on the saved
  // flag, not the local switch. Used for both the Send button and the Enter shortcut.
  const canTest =
    !!testInput.trim() && !!currentFlow?.a2a_enabled && serverA2aEnabled;

  // Re-seed from the flow whenever the modal opens, so it reflects the saved state.
  useEffect(() => {
    if (open) {
      setEnabled(!!currentFlow?.a2a_enabled);
      setForm(overridesToForm(currentFlow?.a2a_card_overrides));
      setTestReply("");
      setTestFailed(false);
    }
  }, [open, currentFlow]);

  const setField = (field: keyof A2ACardForm, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSave = async () => {
    try {
      const updatedFlow = await mutateAsync({
        id: flowId,
        a2a_enabled: enabled,
        a2a_card_overrides: formToOverrides(form),
      });
      if (flows) {
        setFlows(flows.map((f) => (f.id === updatedFlow.id ? updatedFlow : f)));
        setCurrentFlow(updatedFlow);
      }
      setSuccessData({ title: t("a2aModal.saved") });
    } catch (e) {
      setErrorData({
        title: t("a2aModal.saveError"),
        list: [errorDetail(e, "Unknown error")],
      });
    }
  };

  const handleTest = async () => {
    if (!canTest) return;
    setTestReply("");
    setTestFailed(false);
    try {
      const data = await sendMessage({ flowId, message: testInput });
      if (data?.error) {
        setTestFailed(true);
        setTestReply(data.error.message ?? t("a2aModal.testRequestFailed"));
        return;
      }
      setTestReply(parseA2AReply(data?.result) || t("a2aModal.testNoText"));
    } catch (e) {
      setTestFailed(true);
      setTestReply(errorDetail(e, t("a2aModal.testRequestFailed")));
    }
  };

  return (
    <BaseModal open={open} setOpen={setOpen} size="medium">
      <BaseModal.Header description={t("a2aModal.description")}>
        <span className="flex items-center gap-2">
          <ForwardedIconComponent name="Bot" className="h-5 w-5" />
          {t("a2aModal.title")}
        </span>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-5">
          {!serverA2aEnabled && (
            <div className="flex items-center gap-2 rounded-md bg-accent-amber/10 p-2 text-mmd text-accent-amber-foreground">
              <ForwardedIconComponent
                name="AlertTriangle"
                className="h-4 w-4 shrink-0"
              />
              {t("a2aModal.serverDisabled")}
            </div>
          )}
          {!isAgent && (
            <div className="flex items-center gap-2 rounded-md bg-accent-amber/10 p-2 text-mmd text-accent-amber-foreground">
              <ForwardedIconComponent
                name="AlertTriangle"
                className="h-4 w-4 shrink-0"
              />
              {t("a2aModal.notAgent")}
            </div>
          )}

          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-sm font-medium">
                {t("a2aModal.publishLabel")}
              </span>
              <span className="text-mmd text-muted-foreground">
                {t("a2aModal.publishHint")}
              </span>
            </div>
            <Switch
              data-testid="a2a-publish-switch"
              checked={enabled}
              onCheckedChange={setEnabled}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label className="text-mmd font-medium">
              {t("a2aModal.cardUrlLabel")}
            </Label>
            <div className="flex items-center gap-2">
              <Input readOnly value={cardUrl} data-testid="a2a-card-url" />
              <Button
                variant="outline"
                size="icon"
                aria-label={t("a2aModal.copyUrlAria")}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(cardUrl);
                    setSuccessData({ title: t("a2aModal.copied") });
                  } catch {
                    setErrorData({ title: t("a2aModal.copyError") });
                  }
                }}
              >
                <ForwardedIconComponent name="Copy" className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-2">
              <Label className="text-mmd font-medium">
                {t("a2aModal.nameLabel")}
              </Label>
              <Input
                placeholder={currentFlow?.name ?? ""}
                value={form.name}
                onChange={(e) => setField("name", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label className="text-mmd font-medium">
                {t("a2aModal.versionLabel")}
              </Label>
              <Input
                value={form.version}
                onChange={(e) => setField("version", e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label className="text-mmd font-medium">
              {t("a2aModal.descriptionLabel")}
            </Label>
            <Textarea
              className="min-h-16"
              placeholder={currentFlow?.description ?? ""}
              value={form.description}
              onChange={(e) => setField("description", e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-2">
              <Label className="text-mmd font-medium">
                {t("a2aModal.tagsLabel")}
              </Label>
              <Textarea
                className="min-h-16"
                placeholder={t("a2aModal.onePerLine")}
                value={form.tags}
                onChange={(e) => setField("tags", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label className="text-mmd font-medium">
                {t("a2aModal.examplesLabel")}
              </Label>
              <Textarea
                className="min-h-16"
                placeholder={t("a2aModal.onePerLine")}
                value={form.examples}
                onChange={(e) => setField("examples", e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-2 border-t pt-4">
            <Label className="text-mmd font-medium">
              {t("a2aModal.testLabel")}
            </Label>
            {!currentFlow?.a2a_enabled && (
              <span className="text-mmd text-muted-foreground">
                {enabled
                  ? t("a2aModal.testSaveFirst")
                  : t("a2aModal.testPublishFirst")}
              </span>
            )}
            <div className="flex items-center gap-2">
              <Input
                placeholder={t("a2aModal.testPlaceholder")}
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && canTest) handleTest();
                }}
                data-testid="a2a-test-input"
              />
              <Button
                onClick={handleTest}
                loading={isSending}
                disabled={!canTest}
                data-testid="a2a-test-send"
              >
                {t("a2aModal.testSend")}
              </Button>
            </div>
            {testReply && (
              <div
                className={cn(
                  "whitespace-pre-wrap rounded-md p-3 text-mmd",
                  testFailed
                    ? "bg-error-background text-error-foreground"
                    : "bg-muted",
                )}
                data-testid="a2a-test-reply"
              >
                {testReply}
              </div>
            )}
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("a2aModal.save"),
          loading: isPending,
          dataTestId: "a2a-save",
          onClick: handleSave,
        }}
      />
    </BaseModal>
  );
}
