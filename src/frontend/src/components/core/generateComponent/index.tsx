import { memo, useCallback } from "react";
import { usePostGenerateComponentPrompt } from "@/controllers/API/queries/generate-component";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useAddComponent } from "@/hooks/use-add-component";
import useAlertStore from "@/stores/alertStore";
import { useDarkStore } from "@/stores/darkStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useGenerateComponentStore } from "@/stores/generateComponentStore";
import { createFlowComponent, getNodeId } from "@/utils/reactflowUtils";
import GenerateComponentTerminal from "./generate-component-terminal";
import type { GenerateComponentPromptResponse, SubmitResult } from "./types";

function extractSubmitResult(
  response: GenerateComponentPromptResponse,
): SubmitResult {
  let content: string;
  if (response.result) {
    content = response.result;
  } else if (response.text) {
    content = response.text;
  } else if (response.exception_message) {
    throw new Error(response.exception_message);
  } else {
    content = JSON.stringify(response, null, 2);
  }

  const result: SubmitResult = { content };

  if (response.validated !== undefined) {
    result.validated = response.validated;
  }
  if (response.class_name) {
    result.className = response.class_name;
  }
  if (response.validation_error) {
    result.validationError = response.validation_error;
  }
  if (response.validation_attempts) {
    result.validationAttempts = response.validation_attempts;
  }
  if (response.component_code) {
    result.componentCode = response.component_code;
  }

  return result;
}

const GenerateComponent = memo(function GenerateComponent() {
  const isTerminalOpen = useGenerateComponentStore(
    (state) => state.isTerminalOpen,
  );
  const setTerminalOpen = useGenerateComponentStore(
    (state) => state.setTerminalOpen,
  );
  const maxRetries = useGenerateComponentStore((state) => state.maxRetries);
  const setMaxRetries = useGenerateComponentStore(
    (state) => state.setMaxRetries,
  );

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const version = useDarkStore((state) => state.version);
  const { mutateAsync: executePrompt, isPending } =
    usePostGenerateComponentPrompt();
  const { mutateAsync: validateComponentCode } = usePostValidateComponentCode();
  const addComponent = useAddComponent();
  const addFlow = useAddFlow();

  const handleCloseTerminal = useCallback(() => {
    setTerminalOpen(false);
  }, [setTerminalOpen]);

  const handleSubmit = useCallback(
    async (input: string): Promise<SubmitResult> => {
      if (!currentFlowId) {
        throw new Error("No flow selected. Please open a flow first.");
      }

      const response = await executePrompt({
        flowId: currentFlowId,
        inputValue: input,
        maxRetries,
      });

      return extractSubmitResult(response as GenerateComponentPromptResponse);
    },
    [currentFlowId, executePrompt, maxRetries],
  );

  const handleAddToCanvas = useCallback(
    async (code: string) => {
      const response = await validateComponentCode({
        code,
        frontend_node: undefined as never,
      });

      addComponent(response.data, response.type);
    },
    [validateComponentCode, addComponent],
  );

  const handleSaveToSidebar = useCallback(
    async (code: string, className: string) => {
      const response = await validateComponentCode({
        code,
        frontend_node: undefined as never,
      });

      const nodeId = getNodeId(response.type);
      const nodeData = {
        node: response.data,
        showNode: !response.data.minimized,
        type: response.type,
        id: nodeId,
      };

      const flowComponent = createFlowComponent(nodeData, version);
      await addFlow({ flow: flowComponent, override: false });
      setSuccessData({ title: `${className} saved to sidebar` });
    },
    [validateComponentCode, addFlow, version, setSuccessData],
  );

  return (
    <GenerateComponentTerminal
      isOpen={isTerminalOpen}
      onClose={handleCloseTerminal}
      onSubmit={handleSubmit}
      onAddToCanvas={handleAddToCanvas}
      onSaveToSidebar={handleSaveToSidebar}
      isLoading={isPending}
      maxRetries={maxRetries}
      onMaxRetriesChange={setMaxRetries}
    />
  );
});

export default GenerateComponent;
