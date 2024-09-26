// Modals.tsx
import TemplatesModal from "@/modals/templatesModal";
import IconComponent from "../../../../components/genericIconComponent";
import { Button } from "../../../../components/ui/button";
import DeleteConfirmationModal from "../../../../modals/deleteConfirmationModal";
import { cn } from "../../../../utils/utils";

interface ModalsProps {
  openModal: boolean;
  setOpenModal: (value: boolean) => void;
  openDeleteFolderModal: boolean;
  setOpenDeleteFolderModal: (value: boolean) => void;
  handleDeleteFolder: () => void;
}

const ModalsComponent = ({
  openModal,
  setOpenModal,
  openDeleteFolderModal,
  setOpenDeleteFolderModal,
  handleDeleteFolder,
}: ModalsProps) => (
  <>
    {openModal && <TemplatesModal open={openModal} setOpen={setOpenModal} />}
    {openDeleteFolderModal && (
      <DeleteConfirmationModal
        open={openDeleteFolderModal}
        setOpen={setOpenDeleteFolderModal}
        onConfirm={() => {
          handleDeleteFolder();
          setOpenDeleteFolderModal(false);
        }}
        description="folder"
        note={
          "Deleting the selected folder will remove all associated flows and components."
        }
      >
        <Button variant="ghost" size="icon" className={"whitespace-nowrap"}>
          <IconComponent
            data-testid={`delete-folder`}
            name="Trash2"
            className={cn("h-5 w-5")}
          />
        </Button>
      </DeleteConfirmationModal>
    )}
  </>
);

export default ModalsComponent;
