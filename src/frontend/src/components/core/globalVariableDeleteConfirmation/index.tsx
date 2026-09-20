import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { ProviderScopeParams } from "@/controllers/API/helpers/provider-scope";
import { useDeleteGlobalVariables } from "@/controllers/API/queries/variables";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";

interface GlobalVariableDeleteConfirmationProps {
  option: string;
  variableId?: string;
  onConfirmDelete: () => void;
  providerScope?: ProviderScopeParams;
}

const GlobalVariableDeleteConfirmation = ({
  option,
  variableId,
  onConfirmDelete,
  providerScope,
}: GlobalVariableDeleteConfirmationProps) => {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();

  // Resolve the id in the parent query owner. Mounting another scoped query in
  // every option row would refetch stale data, hide the options fail-closed,
  // and recreate the rows in a loop after the request settles.
  function handleDelete() {
    if (variableId !== undefined) {
      mutateDeleteGlobalVariable(
        { id: variableId, ...(providerScope ?? {}) },
        {
          onSuccess: () => {
            onConfirmDelete();
          },
          onError: () => {
            setErrorData({
              title: t("globalVars.errorDeletingVariable"),
              list: [t("globalVars.errorIdNotFound", { name: option })],
            });
          },
        },
      );
    } else {
      setErrorData({
        title: t("globalVars.errorDeletingVariable"),
        list: [t("globalVars.errorIdNotFound", { name: option })],
      });
    }
  }

  return (
    <>
      <DeleteConfirmationModal
        onConfirm={(e) => {
          e.stopPropagation();
          e.preventDefault();
          handleDelete();
        }}
        description={'variable "' + option + '"'}
        asChild
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
          }}
          className="pr-1"
        >
          <ForwardedIconComponent
            name="Trash2"
            className={cn(
              "h-4 w-4 text-primary opacity-0 hover:text-status-red group-hover:opacity-100",
            )}
            aria-hidden="true"
          />
        </button>
      </DeleteConfirmationModal>
    </>
  );
};

export default GlobalVariableDeleteConfirmation;
