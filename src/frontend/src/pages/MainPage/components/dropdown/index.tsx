import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import useAlertStore from "@/stores/alertStore";
import type { FlowType } from "@/types/flow";
import useDuplicateFlow from "../../hooks/use-handle-duplicate";
import useSelectOptionsChange from "../../hooks/use-select-options-change";

type DropdownComponentProps = {
  flowData: FlowType;
  setOpenDelete: (open: boolean) => void;
  handleExport: () => void;
  handleEdit: () => void;
};

const DropdownComponent = ({
  flowData,
  setOpenDelete,
  handleExport,
  handleEdit,
}: DropdownComponentProps) => {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { handleDuplicate } = useDuplicateFlow({ flow: flowData });

  const duplicateFlow = () => {
    handleDuplicate().then(() =>
      setSuccessData({
        title: t("flow.duplicatedSuccess", {
          type: flowData.is_component ? "Component" : "Flow",
        }),
      }),
    );
  };

  const { handleSelectOptionsChange } = useSelectOptionsChange(
    [flowData.id],
    setErrorData,
    setOpenDelete,
    handleExport,
    duplicateFlow,
    handleEdit,
  );

  return (
    <>
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          handleSelectOptionsChange("edit");
        }}
        className="cursor-pointer"
        data-testid="btn-edit-flow"
      >
        <ForwardedIconComponent
          name="SquarePen"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        {t("flow.menu.editDetails")}
      </DropdownMenuItem>
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          handleSelectOptionsChange("export");
        }}
        className="cursor-pointer"
        data-testid="btn-download-json"
      >
        <ForwardedIconComponent
          name="Download"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        {t("flow.menu.export")}
      </DropdownMenuItem>
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          handleSelectOptionsChange("duplicate");
        }}
        className="cursor-pointer"
        data-testid="btn-duplicate-flow"
      >
        <ForwardedIconComponent
          name="CopyPlus"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        {t("flow.menu.duplicate")}
      </DropdownMenuItem>
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          setOpenDelete(true);
        }}
        className="cursor-pointer text-destructive"
        data-testid="btn_delete_dropdown_menu"
      >
        <ForwardedIconComponent
          name="Trash2"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        {t("flow.menu.delete")}
      </DropdownMenuItem>
    </>
  );
};

export default DropdownComponent;
