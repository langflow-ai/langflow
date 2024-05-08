import { FormProvider, useForm } from "react-hook-form";
import ForwardedIconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import BaseModal from "../baseModal";
import FolderForms from "./component";

type FoldersModalProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

export type FolderFormsType = {
  folderName: string;
  folderDescription: string;
  components: string[];
  flows: string[];
};

export default function FoldersModal({
  open,
  setOpen,
}: FoldersModalProps): JSX.Element {
  const { control, setValue, handleSubmit } = useForm<FolderFormsType>();
  const methods = useForm();

  const onSubmit = (data) => {
    console.log(data);
  };

  return (
    <BaseModal size="x-small" open={open} setOpen={setOpen}>
      <BaseModal.Header description={"Add your new folder"}>
        <span className="pr-2" data-testid="modal-title">
          New Folder
        </span>
        <ForwardedIconComponent
          name="FolderPlusIcon"
          className="h-6 w-6 pl-1 text-primary "
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div>
          <FormProvider {...methods}>
            <form onSubmit={handleSubmit(onSubmit)}>
              <FolderForms control={control} setValue={setValue} />
              <Button className="float-right mt-6" type="submit">
                Save Folder
              </Button>
            </form>
          </FormProvider>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
