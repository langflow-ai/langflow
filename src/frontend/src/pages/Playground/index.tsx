import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { v4 as uuid } from "uuid";
import AlertDisplayArea from "@/alerts/displayArea";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { CustomIOModal } from "@/customization/components/custom-new-modal";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import { useDocumentTitle } from "@/hooks/use-document-title";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { type CookieOptions, getCookie, setCookie } from "@/utils/utils";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { getInputsAndOutputs } from "../../utils/storeUtils";
import {
  canOpenPublicPlayground,
  unreachablePlaygroundDestination,
} from "./publicPlaygroundAccess";
export default function PlaygroundPage() {
  useGetConfig({});
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setClientId = useUtilityStore((state) => state.setClientId);

  const { id } = useParams();
  const { mutateAsync: getFlow } = useGetFlow();

  const navigate = useCustomNavigate();

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setIsLoading = useFlowsManagerStore((state) => state.setIsLoading);
  const setPlaygroundPage = useFlowStore((state) => state.setPlaygroundPage);

  useDocumentTitle(currentSavedFlow?.name);

  // The route gate admits anonymous visitors so a public link resolves without
  // a session; if the server declines the link, this is where they are sent.
  // Auth state is read at call time, not captured: this runs from an async
  // effect that was created on the first render, when the store still holds
  // the pre-hydration `autoLogin: null` and would misroute the visitor home.
  const leaveUnreachableFlow = () => {
    const { autoLogin, isAuthenticated } = useAuthStore.getState();
    navigate(
      unreachablePlaygroundDestination({
        flowId: id,
        autoLogin,
        isAuthenticated,
      }),
    );
  };

  async function getFlowData() {
    try {
      const flow = await getFlow({ id: id!, public: true });
      return flow;
    } catch (error) {
      console.error(error);
      leaveUnreachableFlow();
    }
  }

  useEffect(() => {
    const initializeFlow = async () => {
      setIsLoading(true);
      if (currentFlowId === "") {
        const flow = await getFlowData();
        if (flow) {
          setCurrentFlow(flow);
        } else {
          leaveUnreachableFlow();
        }
      }
    };

    initializeFlow();
    setIsLoading(false);
  }, [id]);

  useEffect(() => {
    if (id) track("Playground Page Loaded", { flowId: id });
    setPlaygroundPage(true);
  }, []);

  useEffect(() => {
    if (currentSavedFlow?.data) {
      const { inputs, outputs } = getInputsAndOutputs(
        currentSavedFlow?.data?.nodes || [],
      );
      if (
        (inputs.length === 0 && outputs.length === 0) ||
        !canOpenPublicPlayground(currentSavedFlow)
      ) {
        leaveUnreachableFlow();
      }
    }
  }, [currentSavedFlow]);

  useEffect(() => {
    // Get client ID from cookie or create new one
    const clientId = getCookie("client_id");
    if (!clientId) {
      const newClientId = uuid();
      const cookieOptions: CookieOptions = {
        secure: window.location.protocol === "https:",
        sameSite: "Strict",
      };
      setCookie("client_id", newClientId, cookieOptions);
      setClientId(newClientId);
    } else {
      setClientId(clientId);
    }
  }, []);

  return (
    <main className="flex h-full w-full flex-col items-center justify-center align-middle">
      <div className="fixed bottom-4 left-4 z-[999]">
        <AlertDisplayArea />
      </div>
      {currentSavedFlow && (
        <CustomIOModal
          open={true}
          setOpen={() => {}}
          isPlayground
          playgroundPage
        >
          <></>
        </CustomIOModal>
      )}
    </main>
  );
}
