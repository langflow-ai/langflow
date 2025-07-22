import type { NodeDataType } from '@/types/flow';
import {
  shouldShowAllOutputs,
  separateOutputsByGroup,
  getDisplayOutput,
  determineOutputStatus,
  isOutputEmpty,
  detectLooping,
  isOutputShortcutOpenable,
} from '../nodeOutputUtils';

// Mock the utility functions that are dependencies
jest.mock('../../../../../utils/utils', () => ({
  logFirstMessage: jest.fn((data, outputName) => {
    return data?.outputs?.[outputName]?.message?.length > 0;
  }),
  logHasMessage: jest.fn((data, outputName) => {
    return data?.outputs?.[outputName]?.message?.length > 0;
  }),
  logTypeIsError: jest.fn((data, outputName) => {
    return data?.outputs?.[outputName]?.type === 'error';
  }),
  logTypeIsUnknown: jest.fn((data, outputName) => {
    return data?.outputs?.[outputName]?.type === 'unknown';
  }),
}));

jest.mock('../../../../../utils/reactflowUtils', () => ({
  scapedJSONStringfy: jest.fn(obj => JSON.stringify(obj).replace(/"/g, 'œ')),
  scapeJSONParse: jest.fn(str => {
    try {
      const parsed = str.replace(/œ/g, '"');
      return JSON.parse(parsed);
    } catch {
      return {};
    }
  }),
}));

// Mock data for testing
const mockOutputWithLoop = {
  name: 'output1',
  allows_loop: true,
  group_outputs: false,
};

const mockOutputWithoutLoop = {
  name: 'output2',
  allows_loop: false,
  group_outputs: false,
};

const mockGroupedOutput = {
  name: 'grouped1',
  allows_loop: false,
  group_outputs: true,
};

const mockIndividualOutput = {
  name: 'individual1',
  allows_loop: false,
  group_outputs: false,
};

const mockConditionalRouterData: Partial<NodeDataType> = {
  type: 'ConditionalRouter',
  id: 'test-node',
};

const mockRegularData: Partial<NodeDataType> = {
  type: 'RegularNode',
  id: 'test-node',
};

const mockFlowPoolNode = {
  data: {
    outputs: {
      output1: {
        message: ['test message'],
        type: 'string',
      },
      output2: {
        message: [],
        type: 'unknown',
      },
      output3: {
        message: ['error'],
        type: 'error',
      },
    },
  },
};

const mockEdges = [
  {
    id: 'edge1',
    source: 'test-node',
    target: 'target-node',
    sourceHandle: '{"output":"output1"}',
    targetHandle: '{"input":"input1","output_types":["string"]}',
    data: {
      sourceHandle: { name: 'output1' },
    },
  },
  {
    id: 'edge2',
    source: 'other-node',
    target: 'test-node',
    sourceHandle: '{"output":"output2"}',
    targetHandle: '{"input":"input2"}',
    data: {
      sourceHandle: { name: 'output2' },
    },
  },
];

describe('NodeOutput Utility Functions', () => {
  describe('shouldShowAllOutputs', () => {
    it('should return true when there are loop outputs', () => {
      const outputs = [mockOutputWithLoop, mockOutputWithoutLoop];
      const result = shouldShowAllOutputs(
        outputs,
        mockRegularData as NodeDataType
      );
      expect(result).toBe(true);
    });

    it('should return true for ConditionalRouter type', () => {
      const outputs = [mockOutputWithoutLoop];
      const result = shouldShowAllOutputs(
        outputs,
        mockConditionalRouterData as NodeDataType
      );
      expect(result).toBe(true);
    });

    it('should return false for regular node without loop outputs', () => {
      const outputs = [mockOutputWithoutLoop];
      const result = shouldShowAllOutputs(
        outputs,
        mockRegularData as NodeDataType
      );
      expect(result).toBe(false);
    });

    it('should handle empty outputs array', () => {
      const outputs: any[] = [];
      const result = shouldShowAllOutputs(
        outputs,
        mockRegularData as NodeDataType
      );
      expect(result).toBe(false);
    });
  });

  describe('separateOutputsByGroup', () => {
    it('should correctly separate grouped and individual outputs', () => {
      const outputs = [
        mockGroupedOutput,
        mockIndividualOutput,
        mockOutputWithLoop,
      ];
      const result = separateOutputsByGroup(outputs);

      expect(result.groupedOutputs).toHaveLength(1);
      expect(result.individualOutputs).toHaveLength(2);
      expect(result.groupedOutputs[0]).toEqual(mockGroupedOutput);
      expect(result.individualOutputs).toContain(mockIndividualOutput);
      expect(result.individualOutputs).toContain(mockOutputWithLoop);
    });

    it('should handle all grouped outputs', () => {
      const outputs = [
        mockGroupedOutput,
        { ...mockGroupedOutput, name: 'grouped2' },
      ];
      const result = separateOutputsByGroup(outputs);

      expect(result.groupedOutputs).toHaveLength(2);
      expect(result.individualOutputs).toHaveLength(0);
    });

    it('should handle all individual outputs', () => {
      const outputs = [mockIndividualOutput, mockOutputWithLoop];
      const result = separateOutputsByGroup(outputs);

      expect(result.groupedOutputs).toHaveLength(0);
      expect(result.individualOutputs).toHaveLength(2);
    });

    it('should handle empty outputs array', () => {
      const outputs: any[] = [];
      const result = separateOutputsByGroup(outputs);

      expect(result.groupedOutputs).toHaveLength(0);
      expect(result.individualOutputs).toHaveLength(0);
    });
  });

  describe('getDisplayOutput', () => {
    const groupedOutputs = [
      { name: 'output1', group_outputs: true },
      { name: 'output2', group_outputs: true },
      { name: 'output3', group_outputs: true },
    ];

    it('should return selected output when it exists in grouped outputs', () => {
      const selectedOutput = { name: 'output2' };
      const result = getDisplayOutput(groupedOutputs, selectedOutput);
      expect(result).toEqual(groupedOutputs[1]);
    });

    it('should return first output when selected output is not found', () => {
      const selectedOutput = { name: 'nonexistent' };
      const result = getDisplayOutput(groupedOutputs, selectedOutput);
      expect(result).toEqual(groupedOutputs[0]);
    });

    it('should return first output when no selected output provided', () => {
      const result = getDisplayOutput(groupedOutputs, null);
      expect(result).toEqual(groupedOutputs[0]);
    });

    it('should return first output when selected output is undefined', () => {
      const result = getDisplayOutput(groupedOutputs, undefined);
      expect(result).toEqual(groupedOutputs[0]);
    });

    it('should handle empty grouped outputs array', () => {
      const result = getDisplayOutput([], { name: 'test' });
      expect(result).toBeUndefined();
    });
  });

  describe('determineOutputStatus', () => {
    it('should correctly determine output status when flow pool node exists', () => {
      const flowPool = { 'test-node': [mockFlowPoolNode] };
      const result = determineOutputStatus(flowPool, 'test-node', 'output1');

      expect(result.displayOutputPreview).toBe(true);
      expect(result.unknownOutput).toBe(false);
      expect(result.errorOutput).toBe(false);
    });

    it('should detect unknown output type', () => {
      const flowPool = { 'test-node': [mockFlowPoolNode] };
      const result = determineOutputStatus(flowPool, 'test-node', 'output2');

      expect(result.displayOutputPreview).toBe(false);
      expect(result.unknownOutput).toBe(true);
      expect(result.errorOutput).toBe(false);
    });

    it('should detect error output type', () => {
      const flowPool = { 'test-node': [mockFlowPoolNode] };
      const result = determineOutputStatus(flowPool, 'test-node', 'output3');

      expect(result.displayOutputPreview).toBe(true);
      expect(result.unknownOutput).toBe(false);
      expect(result.errorOutput).toBe(true);
    });

    it('should handle missing flow pool node', () => {
      const flowPool = {};
      const result = determineOutputStatus(flowPool, 'test-node', 'output1');

      expect(result.displayOutputPreview).toBe(false);
      expect(result.unknownOutput).toBe(false);
      expect(result.errorOutput).toBe(false);
    });

    it('should handle empty flow pool for node', () => {
      const flowPool = { 'test-node': [] };
      const result = determineOutputStatus(flowPool, 'test-node', 'output1');

      expect(result.displayOutputPreview).toBe(false);
      expect(result.unknownOutput).toBe(false);
      expect(result.errorOutput).toBe(false);
    });
  });

  describe('isOutputEmpty', () => {
    it('should return true when all outputs have empty messages', () => {
      const nodeData = {
        outputs: {
          output1: { message: [] },
          output2: { message: [] },
        },
      };
      const result = isOutputEmpty(nodeData);
      expect(result).toBe(true);
    });

    it('should return false when any output has messages', () => {
      const nodeData = {
        outputs: {
          output1: { message: [] },
          output2: { message: ['test'] },
        },
      };
      const result = isOutputEmpty(nodeData);
      expect(result).toBe(false);
    });

    it('should return true when outputs object is empty', () => {
      const nodeData = { outputs: {} };
      const result = isOutputEmpty(nodeData);
      expect(result).toBe(true);
    });

    it('should return true when outputs is undefined', () => {
      const nodeData = {};
      const result = isOutputEmpty(nodeData);
      expect(result).toBe(true);
    });

    it('should return true when nodeData is undefined', () => {
      const result = isOutputEmpty(undefined);
      expect(result).toBe(true);
    });
  });

  describe('detectLooping', () => {
    it('should detect looping when edge has output_types in targetHandle', () => {
      const result = detectLooping(mockEdges, '{"output":"output1"}');
      expect(result).toBe(true);
    });

    it('should not detect looping for regular edges', () => {
      const result = detectLooping(mockEdges, '{"output":"output2"}');
      expect(result).toBe(false);
    });

    it('should handle malformed edge data gracefully', () => {
      const edgesWithBadData = [
        {
          id: 'edge1',
          source: 'test-node',
          target: 'target-node',
          sourceHandle: '{"output":"output1"}',
          targetHandle: 'invalid-json',
        },
      ];
      const result = detectLooping(edgesWithBadData, '{"output":"output1"}');
      expect(result).toBe(false);
    });

    it('should return false for empty edges array', () => {
      const result = detectLooping([], '{"output":"output1"}');
      expect(result).toBe(false);
    });
  });

  describe('isOutputShortcutOpenable', () => {
    const mockNodeData = {
      id: 'test-node',
      node: {
        outputs: [{ name: 'output1' }, { name: 'output2' }],
      },
    };

    it('should return true for first output with edges', () => {
      const result = isOutputShortcutOpenable({
        displayOutputPreview: true,
        selected: true,
        edges: mockEdges,
        nodeData: mockNodeData as any,
        id: '{"output":"output1"}',
        flowPoolNode: mockFlowPoolNode,
        internalOutputName: 'output1',
      });
      expect(result).toBe(true);
    });

    it('should return false when not selected', () => {
      const result = isOutputShortcutOpenable({
        displayOutputPreview: true,
        selected: false,
        edges: mockEdges,
        nodeData: mockNodeData as any,
        id: '{"output":"output1"}',
        flowPoolNode: mockFlowPoolNode,
        internalOutputName: 'output1',
      });
      expect(result).toBe(false);
    });

    it('should return false when no output preview', () => {
      const result = isOutputShortcutOpenable({
        displayOutputPreview: false,
        selected: true,
        edges: mockEdges,
        nodeData: mockNodeData as any,
        id: '{"output":"output1"}',
        flowPoolNode: mockFlowPoolNode,
        internalOutputName: 'output1',
      });
      expect(result).toBe(false);
    });

    it('should return true for first message when no edges', () => {
      const result = isOutputShortcutOpenable({
        displayOutputPreview: true,
        selected: true,
        edges: [],
        nodeData: mockNodeData as any,
        id: '{"output":"output1"}',
        flowPoolNode: mockFlowPoolNode,
        internalOutputName: 'output1',
      });
      expect(result).toBe(true);
    });

    it('should handle missing node outputs', () => {
      const nodeDataWithoutOutputs = {
        id: 'test-node',
        node: {},
      };
      const result = isOutputShortcutOpenable({
        displayOutputPreview: true,
        selected: true,
        edges: mockEdges,
        nodeData: nodeDataWithoutOutputs as any,
        id: '{"output":"output1"}',
        flowPoolNode: mockFlowPoolNode,
        internalOutputName: 'output1',
      });
      expect(result).toBe(false);
    });
  });
});
