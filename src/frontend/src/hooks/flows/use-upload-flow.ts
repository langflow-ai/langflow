import { createFileUpload } from "@/helpers/create-file-upload";
import { getObjectsFromFilelist } from "@/helpers/get-objects-from-filelist";
import useFlowStore from "@/stores/flowStore";
import type { FlowType } from "@/types/flow";
import { processDataFromFlow } from "@/utils/reactflowUtils";
import useAddFlow from "./use-add-flow";

const useUploadFlow = () => {
  const addFlow = useAddFlow();
  const paste = useFlowStore((state) => state.paste);

  const getFlowsFromFiles = async ({
    files,
  }: {
    files: File[];
  }): Promise<FlowType[]> => {
    const objectList = await getObjectsFromFilelist<any>(files);
    const flows: FlowType[] = [];
    objectList.forEach((object) => {
      if (object.flows) {
        object.flows.forEach((flow: FlowType) => {
          flows.push(flow);
        });
      } else {
        flows.push(object as FlowType);
      }
    });
    return flows;
  };

  const getFlowsToUpload = async ({
    files,
  }: {
    files?: File[];
  }): Promise<FlowType[]> => {
    if (!files) {
      files = await createFileUpload();
    }
    if (!files.every((file) => file.type === "application/json")) {
      throw new Error("Invalid file type");
    }
    return await getFlowsFromFiles({
      files,
    });
  };

  const uploadFlow = async ({
    files,
    isComponent,
    position,
  }: {
    files?: File[];
    isComponent?: boolean;
    position?: { x: number; y: number };
  }): Promise<void> => {
    try {
      const flows = await getFlowsToUpload({ files });
      for (const flow of flows) {
        await processDataFromFlow(flow);
      }

      if (
        isComponent !== undefined &&
        flows.every(
          (fileData) =>
            (!fileData.is_component && isComponent === true) ||
            (fileData.is_component !== undefined &&
              fileData.is_component !== isComponent),
        )
      ) {
        throw new Error(
          "You cannot upload a component as a flow or vice versa",
        );
      } else {
        let currentPosition = position;
        for (const flow of flows) {
          if (flow.data) {
            if (currentPosition) {
              paste(flow.data, currentPosition);
              currentPosition = {
                x: currentPosition.x + 50,
                y: currentPosition.y + 50,
              };
            } else {
              await addFlow({ flow });
            }
          } else {
            throw new Error("Invalid flow data");
          }
        }
      }
    } catch (e) {
      throw e;
    }
  };

  return uploadFlow;
};

export default useUploadFlow;
