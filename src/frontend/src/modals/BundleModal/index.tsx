import { usePostFolders } from "@/controllers/API/queries/folders";
import { updateFolder } from "@/pages/MainPage/services";
import useAlertStore from "@/stores/alertStore";
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
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);

  const { mutate: mutateAddFolder } = usePostFolders();

  const onSubmit = (data) => {
    if (folderToEdit) {
      updateFolder(data, folderToEdit?.id!).then(
        () => {
          setSuccessData({
            title: "Folder updated successfully.",
          });
          getFoldersApi(true);
          setOpen(false);
        },
        (reason) => {
          if (reason) {
            setErrorData({
              title: `Error updating folder.`,
            });
            console.error(reason);
          } else {
            getFoldersApi(true);
            setOpen(false);
          }
        },
      );
    } else {
      mutateAddFolder(
        {
          data,
        },
        {
          onSuccess: () => {
            setSuccessData({
              title: "Folder created successfully.",
            });
            getFoldersApi(true);
            setOpen(false);
          },
          onError: () => {
            setErrorData({
              title: `Error creating folder.`,
            });
          },
        },
      );
    }
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
