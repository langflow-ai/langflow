import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateDataset } from "@/controllers/API/queries/datasets/use-create-dataset";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import BaseModal from "../baseModal";

interface CreateDatasetModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}

export default function CreateDatasetModal({
  open,
  setOpen,
}: CreateDatasetModalProps): JSX.Element {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const navigate = useCustomNavigate();

  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const createDatasetMutation = useCreateDataset({
    onSuccess: (data) => {
      setSuccessData({ title: "Dataset created successfully" });
      setOpen(false);
      setName("");
      setDescription("");
      navigate(`/assets/datasets/${data.id}`);
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to create dataset",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
    },
  });

  const handleSubmit = () => {
    if (!name.trim()) {
      setErrorData({
        title: "Validation error",
        list: ["Dataset name is required"],
      });
      return;
    }

    createDatasetMutation.mutate({
      name: name.trim(),
      description: description.trim() || undefined,
    });
  };

  const handleClose = () => {
    setOpen(false);
    setName("");
    setDescription("");
  };

  if (!open) return <></>;

  return (
    <BaseModal
      open={open}
      setOpen={handleClose}
      size="small-update"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description="Create a new dataset to store input/output pairs for evaluation.">
        Create Dataset
      </BaseModal.Header>
      <BaseModal.Content className="flex flex-col gap-4 p-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="dataset-name">
            Name <span className="text-destructive">*</span>
          </Label>
          <Input
            id="dataset-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter dataset name"
            autoFocus
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="dataset-description">Description</Label>
          <Textarea
            id="dataset-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Enter dataset description (optional)"
            rows={3}
          />
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Create Dataset",
          loading: createDatasetMutation.isPending,
          disabled: !name.trim() || createDatasetMutation.isPending,
          dataTestId: "btn-create-dataset",
        }}
      />
    </BaseModal>
  );
}
