import { v5 as uuidv5 } from "uuid";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";

export const useGetFlowId = () => {
  const clientId = useUtilityStore((state) => state.clientId);
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const playgroundPage = useFlowStore((state) => state.playgroundPage);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const userData = useAuthStore((state) => state.userData);

  if (!playgroundPage) return realFlowId;

  if (isAuthenticated && autoLogin === false && userData?.id) {
    return uuidv5(`${userData.id}_${realFlowId}`, uuidv5.DNS);
  }

  return uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS);
};
