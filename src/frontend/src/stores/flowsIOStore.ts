import { cloneDeep } from "lodash";
import { create } from "zustand";
import { FlowType, NodeDataType, NodeType } from "../types/flow";
import useFlowStore from "./flowStore";
import { isInputNode, isOutputNode } from "../utils/reactflowUtils";
import useFlowsManagerStore from "./flowsManagerStore";
import useAlertStore from "./alertStore";
import { flowIOStoreType } from "../types/zustand/flowIOStore";
import { buildVertices } from "../utils/buildUtils";
/* const { getNodeId, saveFlow } = useContext(FlowsContext);
const { setErrorData, setNoticeData } = useContext(alertContext); */

const { reactFlowInstance, paste } = useFlowStore();
const { saveFlow } = useFlowsManagerStore();
const { setErrorData, setNoticeData } = useAlertStore();

const useFlowIOStore = create<flowIOStoreType>((set, get) => ({
    flowPool: {},
    getFilterEdge: [],
    isBuilt: false,
    outputTypes: [],
    inputTypes: [],
    inputIds: [],
    outputIds: [],
    isBuilding: true,
    actualFlow: null,

    setFilterEdge: (filterEdge) => { set({getFilterEdge: filterEdge}) },
    setFlowPool: (flowPool) => { set({flowPool}) },
    setIsBuilt: (isBuilt) => { set({isBuilt}) },
    setOutputTypes: (outputTypes) => { set({outputTypes}) },
    setInputTypes: (inputTypes) => { set({inputTypes}) },
    setInputIds: (inputIds) => { set({ inputIds }) },
    setOutputIds: (outputIds) => { set({outputIds}) },
    setIsBuilding: (isBuilding) => { set({isBuilding}) },

    updateFlowPoolNodes: (nodes: NodeType[]) => {
      //this function will update the removing the old ones
      const nodeIdsSet = new Set(nodes.map((node) => node.id));
      set((state) => {
        let newFlowPool = cloneDeep({ ...state.flowPool });
        Object.keys(newFlowPool).forEach((nodeId) => {
          if (!nodeIdsSet.has(nodeId)) {
            delete newFlowPool[nodeId];
          }
        });
        return { flowPool: newFlowPool };
      });
    },
    addDataToFlowPool: (data: any, nodeId: string) => {
        set((state) => {
          let newFlowPool = cloneDeep({ ...state.flowPool });
          if (!newFlowPool[nodeId]) newFlowPool[nodeId] = [data];
          else {
            newFlowPool[nodeId].push(data);
          }
          return { flowPool: newFlowPool };
        });
    },
    CleanFlowPool: () => {
      set({ flowPool: {} });
    },
    updateNodeFlowData: (nodeId: string, newData: NodeDataType) => {
        let oldNodes = reactFlowInstance?.getNodes();
        let targetNode = oldNodes?.find((node) => node.id === nodeId);
        if (targetNode) {
          targetNode.data = cloneDeep(newData);
          reactFlowInstance?.setNodes([...oldNodes!]);
          console.log(
            "after reactflow update",
            JSON.parse(JSON.stringify(reactFlowInstance?.toObject()))
          );
        }
    },
    checkInputandOutput: (flow?: FlowType) => {
        let has_input = false;
        let has_output = false;
        if (!flow && !reactFlowInstance) {
          return false;
        }
        const nodes = flow?.data?.nodes
          ? flow.data.nodes
          : reactFlowInstance!.getNodes();
        nodes.forEach((node) => {
          const nodeData: NodeDataType = node.data as NodeDataType;
          if (isInputNode(nodeData)) {
            has_input = true;
          }
          if (isOutputNode(nodeData)) {
            has_output = true;
          }
        });
        return has_input && has_output;
    },
    getInputTypes: (flow?: FlowType) => {
        let inputType: string[] = [];
        if (!flow && !reactFlowInstance) {
          return [];
        }
        const nodes = flow?.data?.nodes
          ? flow.data.nodes
          : reactFlowInstance!.getNodes();
        nodes.forEach((node) => {
          const nodeData: NodeDataType = node.data as NodeDataType;
          if (isInputNode(nodeData)) {
            // TODO remove count and ramdom key from type before pushing
            inputType.push(nodeData.type);
          }
        });
        set({ inputTypes: inputType });
        return inputType;
    },
    getOutputTypes: (flow?: FlowType) => {
        let outputType: string[] = [];
        if (!flow && !reactFlowInstance) {
          return [];
        }
        const nodes = flow?.data?.nodes
          ? flow.data.nodes
          : reactFlowInstance!.getNodes();
        nodes.forEach((node) => {
          const nodeData: NodeDataType = node.data as NodeDataType;
          if (isOutputNode(nodeData)) {
            // TODO remove count and ramdom key from type before pushing
            outputType.push(nodeData.type);
          }
        });
        set({ outputTypes: outputType });
        return outputType;
    },
    getInputIds: (flow?: FlowType) => {
        let inputIds: string[] = [];
        if (!flow && !reactFlowInstance) {
          return [];
        }
        const nodes = flow?.data?.nodes
          ? flow.data.nodes
          : reactFlowInstance!.getNodes();
        nodes.forEach((node) => {
          const nodeData: NodeDataType = node.data as NodeDataType;
          if (isInputNode(nodeData)) {
            inputIds.push(nodeData.id);
          }
        });
        set({ inputIds });
        return inputIds;
    },
    getOutputIds: (flow?: FlowType) => {
        let outputIds: string[] = [];
        if (!flow && !reactFlowInstance) {
          return [];
        }
        const nodes = flow?.data?.nodes
          ? flow.data.nodes
          : reactFlowInstance!.getNodes();
    
        nodes.forEach((node) => {
          const nodeData: NodeDataType = node.data as NodeDataType;
          if (isOutputNode(nodeData)) {
            outputIds.push(nodeData.id);
          }
        });
        set({ outputIds });
        return outputIds;
    },
    pasteFileOnFLow: async (file?: File) => {
        if (file) {
          const text = await file.text();
          let fileData = JSON.parse(text);
          if (fileData.flows) {
            fileData.flows.forEach((flow: FlowType) => {
              paste(
                { nodes: flow!.data!.nodes, edges: flow!.data!.edges },
                { x: 10, y: 10 }
              );
            });
          } else {
            let flow: FlowType = JSON.parse(text);
            paste(
              { nodes: flow.data!.nodes, edges: flow.data!.edges },
              { x: 10, y: 10 }
            );
          }
        } else {
          const input = document.createElement("input");
          input.type = "file";
          input.accept = ".json";
          // add a change event listener to the file input
          input.onchange = async (e: Event) => {
            if (
              (e.target as HTMLInputElement).files![0].type === "application/json"
            ) {
              const currentfile = (e.target as HTMLInputElement).files![0];
              get().pasteFileOnFLow(currentfile);
            }
          };
          // trigger the file input click event to open the file dialog
          input.click();
        }
      },
      downloadFlow: (
        flow: FlowType,
        flowName: string,
        flowDescription?: string
      ) => {
        // create a data URI with the current flow data
        const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
          JSON.stringify({ ...flow, name: flowName, description: flowDescription })
        )}`;
    
        // create a link element and set its properties
        const link = document.createElement("a");
        link.href = jsonString;
        link.download = `${flowName && flowName != "" ? flowName : "flow"}.json`;
    
        // simulate a click on the link element to trigger the download
        link.click();
      },
    buildFlow: async (nodeId?: string) => {
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
    },
}));

export default useFlowIOStore;
