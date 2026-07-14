import { isAxiosError } from "axios";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { usePostTeamTemplate } from "@/controllers/API/queries/team-templates";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import BaseModal from "../baseModal";

interface SaveTeamTemplateModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}

export default function SaveTeamTemplateModal({
  open,
  setOpen,
}: SaveTeamTemplateModalProps) {
  const { t } = useTranslation();
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const saveFlow = useSaveFlow();
  const { mutateAsync: createTemplate, isPending } = usePostTeamTemplate();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("assistants");
  const [tags, setTags] = useState("");
  const [saving, setSaving] = useState(false);
  const initializedFlowId = useRef<string | null>(null);

  useEffect(() => {
    if (!open) {
      initializedFlowId.current = null;
      return;
    }
    if (currentFlow?.id && initializedFlowId.current !== currentFlow.id) {
      setName(currentFlow?.name ?? "");
      setDescription(currentFlow?.description ?? "");
      setTags(currentFlow?.tags?.join(", ") ?? "");
      initializedFlowId.current = currentFlow.id;
    }
  }, [open, currentFlow]);

  const handleSubmit = async () => {
    if (!currentFlow?.id || !name.trim()) return;
    setSaving(true);
    try {
      await saveFlow();
      const response = await createTemplate({
        source_flow_id: currentFlow.id,
        name: name.trim(),
        description: description.trim() || undefined,
        category,
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean)
          .slice(0, 10),
      });
      setSuccessData({
        title: t("teamTemplates.saved", {
          count: response.cleared_fields,
        }),
      });
      setOpen(false);
    } catch (error: unknown) {
      const detail = isAxiosError<{ detail?: string }>(error)
        ? (error.response?.data?.detail ?? error.message)
        : error instanceof Error
          ? error.message
          : "Unknown error";
      setErrorData({
        title: t("teamTemplates.saveFailed"),
        list: [detail],
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <BaseModal
      size="small-h-full"
      open={open}
      setOpen={setOpen}
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description={t("teamTemplates.securityNotice")}>
        <span className="pr-2">{t("teamTemplates.saveAs")}</span>
        <IconComponent name="LayoutTemplate" className="h-5 w-5" />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4">
          <div className="grid gap-2">
            <Label htmlFor="team-template-name">
              {t("teamTemplates.name")}
            </Label>
            <Input
              id="team-template-name"
              value={name}
              maxLength={100}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="team-template-description">
              {t("teamTemplates.description")}
            </Label>
            <Textarea
              id="team-template-description"
              value={description}
              maxLength={500}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="team-template-category">
              {t("teamTemplates.category")}
            </Label>
            <select
              id="team-template-category"
              className="h-10 rounded-md border bg-background px-3 text-sm"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="assistants">
                {t("templatesModal.assistants")}
              </option>
              <option value="classification">
                {t("templatesModal.classification")}
              </option>
              <option value="coding">{t("templatesModal.coding")}</option>
              <option value="content-generation">
                {t("templatesModal.contentGeneration")}
              </option>
              <option value="q-a">{t("templatesModal.qa")}</option>
              <option value="chatbots">{t("templatesModal.prompting")}</option>
              <option value="rag">{t("templatesModal.rag")}</option>
              <option value="agents">{t("templatesModal.agents")}</option>
            </select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="team-template-tags">
              {t("teamTemplates.tags")}
            </Label>
            <Input
              id="team-template-tags"
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder={t("teamTemplates.tagsPlaceholder")}
            />
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("teamTemplates.saveAs"),
          loading: saving || isPending,
          disabled: !currentFlow?.id || !name.trim(),
          dataTestId: "save-team-template-submit",
        }}
      />
    </BaseModal>
  );
}
