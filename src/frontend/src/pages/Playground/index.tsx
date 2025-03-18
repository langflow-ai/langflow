import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import IOModal from "@/modals/IOModal/new-modal";
import useFlowStore from "@/stores/flowStore";
import { useStoreStore } from "@/stores/storeStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { CookieOptions, getCookie, setCookie } from "@/utils/utils";
import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { v4 as uuid } from "uuid";
import { getComponent } from "../../controllers/API";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import cloneFLowWithParent, {
  getInputsAndOutputs,
} from "../../utils/storeUtils";
export default function PlaygroundPage() {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setClientId = useUtilityStore((state) => state.setClientId);

  const { id } = useParams();
  const { mutateAsync: getFlow } = useGetFlow();

  const navigate = useCustomNavigate();

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setIsLoading = useFlowsManagerStore((state) => state.setIsLoading);

  async function getFlowData() {
    try {
      const flow = await getFlow({ id: id!, public: true });
      return flow;
    } catch (error: any) {
      console.log(error);
      navigate("/");
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
          navigate("/");
        }
      }
    };

    initializeFlow();
    setIsLoading(false);
  }, [id]);

  useEffect(() => {
    if (id) track("Playground Page Loaded", { flowId: id });
  }, []);

  useEffect(() => {
    document.title = currentSavedFlow?.name || "Langflow";
    if (currentSavedFlow?.data) {
      const { inputs, outputs } = getInputsAndOutputs(
        currentSavedFlow?.data?.nodes || [],
      );
      if (
        (inputs.length === 0 && outputs.length === 0) ||
        currentSavedFlow?.access_type !== "PUBLIC"
      ) {
        // redirect to the home page
        navigate("/");
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
    <div className="flex h-full w-full flex-col items-center justify-center align-middle">
      {currentSavedFlow && (
        <IOModal open={true} setOpen={() => {}} isPlayground playgroundPage>
          <></>
        </IOModal>
      )}
    </div>
  );
}
