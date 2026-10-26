import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Dataset } from "@/controllers/API/queries/evals/types";
import { useCreateDataset } from "@/controllers/API/queries/evals/use-datasets";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";

interface CreateDatasetDialogProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  onCreated: (dataset: Dataset) => void;
}

export default function CreateDatasetDialog({
  open,
  setOpen,
  onCreated,
}: CreateDatasetDialogProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const createDataset = useCreateDataset();

  const handleCreate = () => {
    createDataset.mutate(
      { name: name.trim(), description: description.trim() || undefined },
      {
        onSuccess: (dataset) => {
          setName("");
          setDescription("");
          setOpen(false);
          onCreated(dataset);
        },
        onError: (error) =>
          setErrorData({
            title: t("evals.datasets.createError"),
            list: extractApiErrorMessages(error),
          }),
      },
    );
  };

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="x-small"
      onSubmit={handleCreate}
    >
      <BaseModal.Header description={t("evals.datasets.createDescription")}>
        <ForwardedIconComponent name="Table" className="mr-2 h-4 w-4" />
        {t("evals.datasets.createTitle")}
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="dataset-name">{t("evals.datasets.name")}</Label>
            <Input
              id="dataset-name"
              data-testid="dataset-name-input"
              value={name}
              maxLength={255}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="dataset-description">
              {t("evals.datasets.description")}
            </Label>
            <Textarea
              id="dataset-description"
              value={description}
              maxLength={2000}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("evals.datasets.create"),
          loading: createDataset.isPending,
          disabled: !name.trim(),
          dataTestId: "dataset-create-submit",
        }}
      />
    </BaseModal>
  );
}
