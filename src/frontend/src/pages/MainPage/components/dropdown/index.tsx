import ForwardedIconComponent from "@/components/genericIconComponent";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import useAlertStore from "@/stores/alertStore";
import { FlowType } from "@/types/flow";
import { downloadFlow } from "@/utils/reactflowUtils";
import useDuplicateFlows from "../../oldComponents/componentsComponent/hooks/use-handle-duplicate";
import useSelectOptionsChange from "../../oldComponents/componentsComponent/hooks/use-select-options-change";

type DropdownComponentProps = {
  flowData: FlowType;
  setOpenDelete: (open: boolean) => void;
  handlePlaygroundClick?: () => void;
};

const DropdownComponent = ({
  flowData,
  setOpenDelete,
  handlePlaygroundClick,
}: DropdownComponentProps) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { handleDuplicate } = useDuplicateFlows(
    [flowData.id],
    [flowData],
    () => {},
    setSuccessData,
    () => {},
    () => {},
    "flow",
  );

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
      {/* <DropdownMenuItem onClick={() => {}} className="cursor-pointer">
        <ForwardedIconComponent
          name="square-pen"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        Edit details
      </DropdownMenuItem> */}
      {/* {handlePlaygroundClick && (
        <DropdownMenuItem
          onClick={(e) => {
            e.stopPropagation();
            handlePlaygroundClick();
          }}
          className="cursor-pointer sm:hidden"
        >
          <ForwardedIconComponent
            name="play"
            aria-hidden="true"
            className="mr-2 h-4 w-4"
          />
          Playground
        </DropdownMenuItem>
      )} */}
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          handleSelectOptionsChange("export");
        }}
        className="cursor-pointer"
        data-testid="btn-download-json"
      >
        <ForwardedIconComponent
          name="download"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        Download JSON
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
          name="copy-plus"
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
        className="cursor-pointer text-red-500 focus:text-red-500 dark:text-red-500 dark:focus:text-red-500"
      >
        <ForwardedIconComponent
          name="trash"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        Delete
      </DropdownMenuItem>
    </>
  );
};

export default DropdownComponent;
