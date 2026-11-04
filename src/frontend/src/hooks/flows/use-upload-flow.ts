import { usePostUploadFlows } from "@/controllers/API/queries/flows/use-post-upload-flows";
import { createFileUpload } from "@/helpers/create-file-upload";
import { getObjectsFromFilelist } from "@/helpers/get-objects-from-filelist";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import type { FlowType } from "@/types/flow";
import {
  extractFieldsFromComponenents,
  processDataFromFlow,
  processFlows,
} from "@/utils/reactflowUtils";
import usePrepareFlows from "./use-prepare-flows";

const useUploadFlow = () => {
  const prepareFlows = usePrepareFlows();
  const { mutateAsync: postUploadFlows } = usePostUploadFlows();
  const paste = useFlowStore((state) => state.paste);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);

  const getFlowsFromFiles = async ({
    files,
  }: {
    files: File[];
  }): Promise<FlowType[]> => {
    const objectList = await getObjectsFromFilelist<
      FlowType | { flows: FlowType[] }
    >(files);
    const flows: FlowType[] = [];
    objectList.forEach((object) => {
      if (object && "flows" in object && Array.isArray(object.flows)) {
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
    const flows = await getFlowsToUpload({ files });
    if (flows.some((flow) => !flow?.data)) {
      throw new Error("Invalid flow data");
    }
    if (
      isComponent !== undefined &&
      flows.some((flow) => (flow.is_component ?? false) !== isComponent)
    ) {
      throw new Error("You cannot upload a component as a flow or vice versa");
    }
    if (flows.length === 0) return;

    if (position) {
      for (const flow of flows) {
        await processDataFromFlow(flow);
      }
      let currentPosition = position;
      for (const flow of flows) {
        paste(flow.data!, currentPosition);
        currentPosition = {
          x: currentPosition.x + 50,
          y: currentPosition.y + 50,
        };
      }
      return;
    }

    const preparedFlows = await prepareFlows(flows);
    const createdFlows = await postUploadFlows(preparedFlows);
    const { data, flows: myFlows } = processFlows([
      ...createdFlows,
      ...(useFlowsManagerStore.getState().flows ?? []),
    ]);
    setFlows(myFlows);
    useTypesStore.setState((state) => ({
      data: { ...state.data, saved_components: data },
      ComponentFields: extractFieldsFromComponenents({
        ...state.data,
        saved_components: data,
      }),
    }));
  };

  return uploadFlow;
};

export default useUploadFlow;
