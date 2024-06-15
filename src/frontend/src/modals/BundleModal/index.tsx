import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import ForwardedIconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Form } from "../../components/ui/form";
import { useFolderStore } from "../../stores/foldersStore";
import BaseModal from "../baseModal";
import FolderForms from "./component";
import { FolderFormsSchema } from "./entities";
import useFolderSubmit from "./hooks/submit-folder";

type FoldersModalProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

export default function FoldersModal({
  open,
  setOpen,
}: FoldersModalProps): JSX.Element {
  const form = useForm<z.infer<typeof FolderFormsSchema>>({
    resolver: zodResolver(FolderFormsSchema),
    defaultValues: {
      name: "",
      description: "",
      components: [],
      flows: [],
    },
    mode: "all",
  });

  const folderToEdit = useFolderStore((state) => state.folderToEdit);
  const { onSubmit: onSubmitFolder } = useFolderSubmit(setOpen, folderToEdit);

  const onSubmit = (data) => {
    onSubmitFolder(data);
  };

  return (
    <>
      <BaseModal size="x-small" open={open} setOpen={setOpen}>
        <BaseModal.Header
          description={`${folderToEdit ? "Edit a folder" : "Add a new folder"}`}
        >
          <span className="pr-2" data-testid="modal-title">
            {folderToEdit ? "Edit" : "New"} Folder
          </span>
          <ForwardedIconComponent
            name="Plus"
            className="h-6 w-6 pl-1 text-primary"
            aria-hidden="true"
          />
        </BaseModal.Header>
        <BaseModal.Content>
          <div>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)}>
                <FolderForms
                  folderToEdit={folderToEdit}
                  control={form.control}
                  setValue={form.setValue}
                />

                <Button
                  className="float-right mt-6"
                  type="submit"
                  disabled={!form.formState.isValid}
                >
                  {folderToEdit ? "Edit" : "Save"} Folder
                </Button>
              </form>
            </Form>
          </div>
        </BaseModal.Content>
      </BaseModal>
    </>
  );
}
