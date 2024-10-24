import ForwardedIconComponent from "@/components/genericIconComponent";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { usePostDownloadMultipleFlows } from "@/controllers/API/queries/flows";
import useAlertStore from "@/stores/alertStore";
import { FlowType } from "@/types/flow";
import useDuplicateFlows from "../componentsComponent/hooks/use-handle-duplicate";
import useSelectOptionsChange from "../componentsComponent/hooks/use-select-options-change";

type DropdownComponentProps = {
  flowData: FlowType;
  setOpenDelete: (open: boolean) => void;
};

const DropdownComponent = ({
  flowData,
  setOpenDelete,
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

  const { mutate: mutateDownloadMultipleFlows } =
    usePostDownloadMultipleFlows();

  const handleExport = () => {
    mutateDownloadMultipleFlows(
      {
        flow_ids: [flowData.id],
      },
      {
        onSuccess: (data) => {
          const blobType = "application/json";
          const fileNameSuffix = `${flowData.name}.json`;
          const blob = new Blob([data], { type: blobType });

          const link = document.createElement("a");
          link.href = window.URL.createObjectURL(blob);

          let current_time = new Date().toISOString().replace(/[:.]/g, "");

          current_time = current_time
            .replace(/-/g, "")
            .replace(/T/g, "")
            .replace(/Z/g, "");

          link.download = `${fileNameSuffix}`;

          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);

          setSuccessData({ title: `${flowData.name} exported successfully` });
        },
      },
    );
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
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          handleSelectOptionsChange("export");
        }}
        className="cursor-pointer"
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
