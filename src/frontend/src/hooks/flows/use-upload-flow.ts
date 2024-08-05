import useFlowStore from "@/stores/flowStore";
import { FlowType } from "@/types/flow";
import useAddFlow from "./use-add-flow";

const useUploadFlow = () => {
  const addFlow = useAddFlow();
  const paste = useFlowStore((state) => state.paste);

  const getFlowsFromFiles = async ({
    files,
  }: {
    files: FileList;
  }): Promise<FlowType[]> => {
    const fileList: File[] = [];
    if (!fileList.every((file) => file.type === "application/json")) {
      throw new Error("Invalid file format");
    }
    for (let i = 0; i < files.length; i++) {
      fileList.push(files[i]);
    }
    let flows: FlowType[] = [];
    fileList.forEach(async (file) => {
      let text = await file.text();
      let fileData = await JSON.parse(text);
      if (fileData.flows) {
        fileData.flows.forEach((flow: FlowType) => {
          flows.push(flow);
        });
      } else {
        flows.push(fileData as FlowType);
      }
    });
    return flows;
  };

  const getFlowsToUpload = async ({
    files,
  }: {
    files?: FileList;
  }): Promise<FlowType[]> => {
    return new Promise(async (resolve, reject) => {
      if (files) {
        const flows = await getFlowsFromFiles({ files });
        resolve(flows);
      } else {
        // create a file input
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".json";
        // add a change event listener to the file input
        input.onchange = async (e: Event) => {
          const flows = await getFlowsFromFiles({
            files: (e.target as HTMLInputElement).files!,
          });
          resolve(flows);
        };
        // trigger the file input click event to open the file dialog
        input.click();
      }
    });
  };

  const uploadFlow = async ({
    files,
    isComponent,
    position,
  }: {
    files?: FileList;
    isComponent?: boolean;
    position?: { x: number; y: number };
  }): Promise<void> => {
    let flows = await getFlowsToUpload({ files });
    if (
      isComponent !== undefined &&
      flows.every(
        (fileData) =>
          (!fileData.is_component && isComponent === true) ||
          (fileData.is_component !== undefined &&
            fileData.is_component !== isComponent),
      )
    ) {
      throw new Error("You cannot upload a component as a flow or vice versa");
    } else {
      flows.forEach((flow) => {
        if (flow.data) {
          if (position) {
            paste(flow.data, position);
          } else {
            addFlow({ flow });
          }
        } else {
          throw new Error("Invalid flow data");
        }
      });
    }
  };

  return uploadFlow;
};

export default useUploadFlow;
