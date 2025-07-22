import type { NodeDataType } from '@/types/flow';
import { scapeJSONParse } from '../../../../utils/reactflowUtils';
import {
  logFirstMessage,
  logHasMessage,
  logTypeIsError,
  logTypeIsUnknown,
} from '../../../../utils/utils';

/**
 * Determines if all outputs should be shown based on loop outputs and node type
 */
export const shouldShowAllOutputs = (
  outputs: any[],
  data: NodeDataType
): boolean => {
  const hasLoopOutput = outputs.some(output => output.allows_loop);
  const isConditionalRouter = data.type === 'ConditionalRouter';
  return hasLoopOutput || isConditionalRouter;
};

/**
 * Separates outputs into grouped and individual outputs
 */
export const separateOutputsByGroup = (
  outputs: any[]
): { groupedOutputs: any[]; individualOutputs: any[] } => {
  const groupedOutputs = outputs.filter((output: any) => output.group_outputs);
  const individualOutputs = outputs.filter(
    (output: any) => !output.group_outputs
  );
  return { groupedOutputs, individualOutputs };
};

/**
 * Gets the display output for grouped outputs
 */
export const getDisplayOutput = (
  groupedOutputs: any[],
  selectedOutput: any
) => {
  if (groupedOutputs.length === 0) return undefined;

  const outputWithSelection = groupedOutputs.find(
    output => output.name === selectedOutput?.name
  );
  return outputWithSelection || groupedOutputs[0];
};

/**
 * Determines the output status (preview, unknown, error)
 */
export const determineOutputStatus = (
  flowPool: any,
  flowPoolId: string,
  internalOutputName: string
) => {
  const pool = flowPool[flowPoolId] ?? [];
  const flowPoolNode = pool[pool.length - 1];

  if (!flowPoolNode) {
    return {
      displayOutputPreview: false,
      unknownOutput: false,
      errorOutput: false,
    };
  }

  const displayOutputPreview =
    !!flowPool[flowPoolId] &&
    logHasMessage(flowPoolNode?.data, internalOutputName);
  const unknownOutput = logTypeIsUnknown(
    flowPoolNode?.data,
    internalOutputName
  );
  const errorOutput = logTypeIsError(flowPoolNode?.data, internalOutputName);

  return {
    displayOutputPreview,
    unknownOutput,
    errorOutput,
  };
};

/**
 * Checks if all outputs are empty
 */
export const isOutputEmpty = (nodeData: any): boolean => {
  if (!nodeData?.outputs) return true;

  return Object.keys(nodeData.outputs).every(
    key => nodeData.outputs[key]?.message?.length === 0
  );
};

/**
 * Detects if there's a looping edge
 */
export const detectLooping = (edges: any[], sourceHandle: string): boolean => {
  return edges.some(edge => {
    try {
      const targetHandleObject = scapeJSONParse(edge.targetHandle || '{}');
      return (
        targetHandleObject.output_types && edge.sourceHandle === sourceHandle
      );
    } catch {
      return false;
    }
  });
};

/**
 * Determines if output shortcut is openable
 */
export const isOutputShortcutOpenable = ({
  displayOutputPreview,
  selected,
  edges,
  nodeData,
  id,
  flowPoolNode,
  internalOutputName,
}: {
  displayOutputPreview: boolean;
  selected: boolean;
  edges: any[];
  nodeData: any;
  id: string;
  flowPoolNode: any;
  internalOutputName: string;
}): boolean => {
  if (!displayOutputPreview || !selected) return false;

  const hasOutputs =
    nodeData?.node?.outputs && nodeData.node.outputs.length > 0;
  if (!hasOutputs) return false;

  const sortedEdges = [...edges]
    .filter(edge => edge.source === nodeData.id)
    .sort((a, b) => {
      const indexA =
        nodeData?.node?.outputs?.findIndex(
          (output: any) => output.name === a.data?.sourceHandle?.name
        ) ?? 0;
      const indexB =
        nodeData?.node?.outputs?.findIndex(
          (output: any) => output.name === b.data?.sourceHandle?.name
        ) ?? 0;
      return indexA - indexB;
    });

  const isFirstOutput = sortedEdges[0]?.sourceHandle === id;
  const hasNoEdges = !edges.some(edge => edge.source === nodeData.id);
  const isValidFirstMessage =
    hasNoEdges && logFirstMessage(flowPoolNode?.data, internalOutputName);

  return isFirstOutput || isValidFirstMessage;
};
