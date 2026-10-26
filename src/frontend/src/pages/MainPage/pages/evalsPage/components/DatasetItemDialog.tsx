import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { DatasetItem } from "@/controllers/API/queries/evals/types";
import {
  useAddDatasetItems,
  useUpdateDatasetItem,
} from "@/controllers/API/queries/evals/use-datasets";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";

interface DatasetItemDialogProps {
  datasetId: string;
  open: boolean;
  setOpen: (open: boolean) => void;
  item: DatasetItem | null;
}

export default function DatasetItemDialog({
  datasetId,
  open,
  setOpen,
  item,
}: DatasetItemDialogProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [expected, setExpected] = useState("");
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const onError = (error: unknown) =>
    setErrorData({
      title: t("evals.items.saveError"),
      list: extractApiErrorMessages(error),
    });
  const addItems = useAddDatasetItems({ datasetId }, { onError });
  const updateItem = useUpdateDatasetItem({ datasetId }, { onError });

  useEffect(() => {
    if (open) {
      setInput(item?.input ?? "");
      setExpected(item?.expected_output ?? "");
    }
  }, [open, item]);

  const handleSave = () => {
    const expectedOutput = expected.trim() ? expected : null;
    const onSuccess = () => setOpen(false);
    if (item) {
      updateItem.mutate(
        { itemId: item.id, input, expected_output: expectedOutput },
        { onSuccess },
      );
    } else {
      addItems.mutate(
        { items: [{ input, expected_output: expectedOutput }] },
        { onSuccess },
      );
    }
  };

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="small-h-full"
      onSubmit={handleSave}
    >
      <BaseModal.Header description={t("evals.items.dialogDescription")}>
        <ForwardedIconComponent name="ListPlus" className="mr-2 h-4 w-4" />
        {item ? t("evals.items.editTitle") : t("evals.items.addTitle")}
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="item-input">{t("evals.items.input")}</Label>
            <Textarea
              id="item-input"
              data-testid="item-input"
              className="min-h-[100px]"
              value={input}
              onChange={(event) => setInput(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="item-expected">
              {t("evals.items.expectedOptional")}
            </Label>
            <Textarea
              id="item-expected"
              data-testid="item-expected"
              className="min-h-[100px]"
              value={expected}
              onChange={(event) => setExpected(event.target.value)}
            />
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("evals.save"),
          loading: addItems.isPending || updateItem.isPending,
          disabled: !input.trim(),
          dataTestId: "item-save",
        }}
      />
    </BaseModal>
  );
}
