import { Panel } from "@xyflow/react";
import { memo, useCallback, useState } from "react";
import {
  useGetForgeConfig,
  usePostForgePrompt,
} from "@/controllers/API/queries/forge";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useAddComponent } from "@/hooks/use-add-component";
import useAlertStore from "@/stores/alertStore";
import { useDarkStore } from "@/stores/darkStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { createFlowComponent, getNodeId } from "@/utils/reactflowUtils";
import ForgeButton from "./forge-button";
import ForgeTerminal from "./forge-terminal";
import type { ForgePromptResponse, SubmitResult } from "./types";

function extractSubmitResult(response: ForgePromptResponse): SubmitResult {
  // Extract text content
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

  // Build result with validation info if present
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

const ComponentForge = memo(function ComponentForge() {
  const [isTerminalOpen, setIsTerminalOpen] = useState(false);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const version = useDarkStore((state) => state.version);
  const { data: configData } = useGetForgeConfig();
  const { mutateAsync: executePrompt, isPending } = usePostForgePrompt();
  const { mutateAsync: validateComponentCode } = usePostValidateComponentCode();
  const addComponent = useAddComponent();
  const addFlow = useAddFlow();

  const isConfigured = configData?.configured ?? false;

  const handleToggleTerminal = useCallback(() => {
    if (!isConfigured) {
      setErrorData({
        title: "Component Forge requires configuration",
        list: [
          "ANTHROPIC_API_KEY is required to use Component Forge.",
          "Please add it to your environment variables or configure it in Settings > Global Variables.",
        ],
      });
      return;
    }
    setIsTerminalOpen((prev) => !prev);
  }, [isConfigured, setErrorData]);

  const handleCloseTerminal = useCallback(() => {
    setIsTerminalOpen(false);
  }, []);

  const handleSubmit = useCallback(
    async (input: string): Promise<SubmitResult> => {
      if (!currentFlowId) {
        throw new Error("No flow selected. Please open a flow first.");
      }

      const response = await executePrompt({
        flowId: currentFlowId,
        inputValue: input,
      });

      return extractSubmitResult(response as ForgePromptResponse);
    },
    [currentFlowId, executePrompt],
  );

  const handleAddToCanvas = useCallback(
    async (code: string, className: string) => {
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
    <>
      <Panel
        className="!bottom-4 !left-1/2 !top-auto !m-0 -translate-x-1/2"
        position="bottom-center"
      >
        <ForgeButton
          onClick={handleToggleTerminal}
          isTerminalOpen={isTerminalOpen}
        />
      </Panel>

      <ForgeTerminal
        isOpen={isTerminalOpen}
        onClose={handleCloseTerminal}
        onSubmit={handleSubmit}
        onAddToCanvas={handleAddToCanvas}
        onSaveToSidebar={handleSaveToSidebar}
        isLoading={isPending}
      />
    </>
  );
});

export default ComponentForge;
