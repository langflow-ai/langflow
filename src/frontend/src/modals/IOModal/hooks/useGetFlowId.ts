import { v5 as uuidv5 } from "uuid";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";

export const useGetFlowId = () => {
  const clientId = useUtilityStore((state) => state.clientId);
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const playgroundPage = useFlowStore((state) => state.playgroundPage);
  const currentFlowId = playgroundPage
    ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
    : realFlowId;
  return currentFlowId;
};
