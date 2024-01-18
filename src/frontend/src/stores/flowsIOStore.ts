import { create } from "zustand";
import useAlertStore from "./alertStore";
import useFlowStore from "./flowStore";
import useFlowsManagerStore from "./flowsManagerStore";
/* const { getNodeId, saveFlow } = useContext(FlowsContext);
const { setErrorData, setNoticeData } = useContext(alertContext); */

const { reactFlowInstance, paste } = useFlowStore();
const { saveFlow } = useFlowsManagerStore();
const { setErrorData, setNoticeData } = useAlertStore();

const useFlowIOStore = create<any>((set, get) => ({
  /* buildFlow: async (nodeId?: string) => {
        function handleBuildUpdate(data: any) {
          get().addDataToFlowPool(data.data[data.id], data.id);
        }
        console.log(
          "building flow before save",
          JSON.parse(JSON.stringify(get().actualFlow))
        );
        console.log(saveFlow);
        await saveFlow(
          { ...get().actualFlow!, data: reactFlowInstance!.toObject()! },
          true
        );
        console.log(
          "building flow AFTER save",
          JSON.parse(JSON.stringify(get().actualFlow))
        );
        return buildVertices({
          flow: {
            data: reactFlowInstance?.toObject()!,
            description: get().actualFlow!.description,
            id: get().actualFlow!.id,
            name: get().actualFlow!.name,
          },
          nodeId,
          onBuildComplete: () => {
            if (nodeId) {
              setNoticeData({ title: `${nodeId} built successfully` });
            }
          },
          onBuildUpdate: handleBuildUpdate,
          onBuildError: (title, list) => {
            setErrorData({ list, title });
          },
        });
    }, */
}));

export default useFlowIOStore;
