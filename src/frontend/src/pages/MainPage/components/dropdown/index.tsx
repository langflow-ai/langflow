import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import useAlertStore from "@/stores/alertStore";
import { FlowType } from "@/types/flow";
import { downloadFlow } from "@/utils/reactflowUtils";
import useDuplicateFlows from "../../hooks/use-handle-duplicate";
import useSelectOptionsChange from "../../hooks/use-select-options-change";

type DropdownComponentProps = {
  flowData: FlowType;
  setOpenDelete: (open: boolean) => void;
  handlePlaygroundClick?: () => void;
};

const DropdownComponent = ({
  flowData,
  setOpenDelete,
}: DropdownComponentProps) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { handleDuplicate } = useDuplicateFlows({
    selectedFlowsComponentsCards: [flowData.id],
    allFlows: [flowData],
    setSuccessData,
  });

  const handleExport = () => {
    downloadFlow(flowData, flowData.name, flowData.description);
    setSuccessData({ title: `${flowData.name} exported successfully` });
  };

  const { handleSelectOptionsChange } = useSelectOptionsChange(
    [flowData.id],
    setErrorData,
    setOpenDelete,
    handleDuplicate,
    handleExport,
  );

  return (
    <>
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
        Download
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
        Duplicate
      </DropdownMenuItem>
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          setOpenDelete(true);
        }}
        className="cursor-pointer text-destructive"
      >
        <ForwardedIconComponent
          name="Trash2"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        Delete
      </DropdownMenuItem>
    </>
  );
};

export default DropdownComponent;
