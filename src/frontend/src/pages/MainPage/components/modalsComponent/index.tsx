// Modals.tsx
import { useTranslation } from "react-i18next";
import TemplatesModal from "@/modals/templatesModal";
import DeleteConfirmationModal from "../../../../modals/deleteConfirmationModal";

interface ModalsProps {
  openModal: boolean;
  setOpenModal: (value: boolean) => void;
  openDeleteFolderModal: boolean;
  setOpenDeleteFolderModal: (value: boolean) => void;
  handleDeleteFolder: () => void;
}

const ModalsComponent = ({
  openModal = false,
  setOpenModal = () => {},
  openDeleteFolderModal = false,
  setOpenDeleteFolderModal = () => {},
  handleDeleteFolder = () => {},
}: ModalsProps) => {
  const { t } = useTranslation();

  return (
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
          description={t("deleteModal.folder")}
          note={t("deleteModal.noteFolderContents")}
        >
          <></>
        </DeleteConfirmationModal>
      )}
    </>
  );
};

export default ModalsComponent;
