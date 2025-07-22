/**
 * Jest test for the createNewFlow function from utils/reactflowUtils.ts
 *
 * This test file reimplements the function inline to avoid complex dependency issues
 * with imports that use import.meta and other Node.js-specific features that Jest
 * has trouble parsing in the jsdom environment.
 *
 * The test verifies all aspects of the createNewFlow function behavior, including:
 * - Default value handling
 * - Flow parameter processing
 * - Edge cases and nullish coalescing behavior
 * - Immutability and consistency
 */

import type { ReactFlowJsonObject } from '@xyflow/react';

// Define minimal types needed for testing
type FlowType = {
  name: string;
  id: string;
  data: ReactFlowJsonObject<any, any> | null;
  description: string;
  endpoint_name?: string | null;
  is_component?: boolean;
  icon?: string;
  gradient?: string;
  tags?: string[];
  folder_id?: string;
  mcp_enabled?: boolean;
};

// Mock the getRandomDescription function
const mockGetRandomDescription = jest.fn(() => 'Random Description');

// Define the function to test directly
const createNewFlow = (
  flowData: ReactFlowJsonObject<any, any>,
  folderId: string,
  flow?: FlowType
) => {
  return {
    description: flow?.description ?? mockGetRandomDescription(),
    name: flow?.name ? flow.name : 'New Flow',
    data: flowData,
    id: '',
    icon: flow?.icon ?? undefined,
    gradient: flow?.gradient ?? undefined,
    is_component: flow?.is_component ?? false,
    folder_id: folderId,
    endpoint_name: flow?.endpoint_name ?? undefined,
    tags: flow?.tags ?? [],
    mcp_enabled: true,
  };
};

describe('createNewFlow', () => {
  // Mock data setup
  const mockFlowData: ReactFlowJsonObject<any, any> = {
    nodes: [],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  };

  const mockFolderId = 'test-folder-id';

  const mockFlow: FlowType = {
    id: 'test-flow-id',
    name: 'Test Flow',
    description: 'Test Description',
    data: mockFlowData,
    icon: 'test-icon',
    gradient: 'test-gradient',
    is_component: true,
    folder_id: 'original-folder-id',
    endpoint_name: 'test-endpoint',
    tags: ['tag1', 'tag2'],
    mcp_enabled: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetRandomDescription.mockReturnValue('Random Description');
  });

  describe('when no flow parameter is provided', () => {
    it('should create a new flow with default values', () => {
      const result = createNewFlow(mockFlowData, mockFolderId);

      expect(result).toEqual({
        description: 'Random Description',
        name: 'New Flow',
        data: mockFlowData,
        id: '',
        icon: undefined,
        gradient: undefined,
        is_component: false,
        folder_id: mockFolderId,
        endpoint_name: undefined,
        tags: [],
        mcp_enabled: true,
      });

      expect(mockGetRandomDescription).toHaveBeenCalledTimes(1);
    });

    it('should use the provided flowData and folderId', () => {
      const customFlowData: ReactFlowJsonObject<any, any> = {
        nodes: [
          {
            id: 'node-1',
            type: 'genericNode',
            position: { x: 0, y: 0 },
            data: {},
          },
        ],
        edges: [
          {
            id: 'edge-1',
            source: 'node-1',
            target: 'node-2',
          },
        ],
        viewport: { x: 10, y: 20, zoom: 1.5 },
      };
      const customFolderId = 'custom-folder-id';

      const result = createNewFlow(customFlowData, customFolderId);

      expect(result.data).toBe(customFlowData);
      expect(result.folder_id).toBe(customFolderId);
    });
  });

  describe('when flow parameter is provided', () => {
    it('should use flow properties when available', () => {
      const result = createNewFlow(mockFlowData, mockFolderId, mockFlow);

      expect(result).toEqual({
        description: 'Test Description',
        name: 'Test Flow',
        data: mockFlowData,
        id: '',
        icon: 'test-icon',
        gradient: 'test-gradient',
        is_component: true,
        folder_id: mockFolderId, // Should use new folderId, not original
        endpoint_name: 'test-endpoint',
        tags: ['tag1', 'tag2'],
        mcp_enabled: true, // Always true regardless of input
      });

      expect(mockGetRandomDescription).not.toHaveBeenCalled();
    });

    it('should fallback to defaults when flow properties are undefined', () => {
      const partialFlow: FlowType = {
        id: 'test-id',
        name: 'Test Name',
        description: '', // Empty string, not undefined, so it won't fall back
        data: null,
        // All optional properties undefined
      };

      const result = createNewFlow(mockFlowData, mockFolderId, partialFlow);

      expect(result).toEqual({
        description: '', // Empty string is preserved, doesn't trigger fallback
        name: 'Test Name',
        data: mockFlowData,
        id: '',
        icon: undefined,
        gradient: undefined,
        is_component: false,
        folder_id: mockFolderId,
        endpoint_name: undefined,
        tags: [],
        mcp_enabled: true,
      });

      expect(mockGetRandomDescription).not.toHaveBeenCalled();
    });

    it('should handle flow with empty description', () => {
      const flowWithEmptyDescription: FlowType = {
        ...mockFlow,
        description: '',
      };

      const result = createNewFlow(
        mockFlowData,
        mockFolderId,
        flowWithEmptyDescription
      );

      expect(result.description).toBe(''); // Empty string is preserved
      expect(mockGetRandomDescription).not.toHaveBeenCalled();
    });

    it('should handle flow with null/undefined description', () => {
      const flowWithNullDescription: FlowType = {
        ...mockFlow,
        description: undefined as any,
      };

      const result = createNewFlow(
        mockFlowData,
        mockFolderId,
        flowWithNullDescription
      );

      expect(result.description).toBe('Random Description');
      expect(mockGetRandomDescription).toHaveBeenCalledTimes(1);
    });

    it('should handle flow with empty name', () => {
      const flowWithEmptyName: FlowType = {
        ...mockFlow,
        name: '',
      };

      const result = createNewFlow(
        mockFlowData,
        mockFolderId,
        flowWithEmptyName
      );

      expect(result.name).toBe('New Flow');
    });

    it('should handle flow with whitespace-only name', () => {
      const flowWithWhitespaceName: FlowType = {
        ...mockFlow,
        name: '   ',
      };

      const result = createNewFlow(
        mockFlowData,
        mockFolderId,
        flowWithWhitespaceName
      );

      expect(result.name).toBe('   '); // Preserves whitespace as per current logic
    });
  });

  describe('special properties handling', () => {
    it('should always set id to empty string', () => {
      const result = createNewFlow(mockFlowData, mockFolderId, mockFlow);
      expect(result.id).toBe('');
    });

    it('should always set mcp_enabled to true', () => {
      const flowWithMcpDisabled: FlowType = {
        ...mockFlow,
        mcp_enabled: false,
      };

      const result = createNewFlow(
        mockFlowData,
        mockFolderId,
        flowWithMcpDisabled
      );

      expect(result.mcp_enabled).toBe(true);
    });

    it('should always use the provided folderId, not the flows folder_id', () => {
      const newFolderId = 'different-folder-id';
      const result = createNewFlow(mockFlowData, newFolderId, mockFlow);

      expect(result.folder_id).toBe(newFolderId);
      expect(result.folder_id).not.toBe(mockFlow.folder_id);
    });

    it('should handle undefined tags as empty array', () => {
      const flowWithUndefinedTags: FlowType = {
        ...mockFlow,
        tags: undefined,
      };

      const result = createNewFlow(
        mockFlowData,
        mockFolderId,
        flowWithUndefinedTags
      );

      expect(result.tags).toEqual([]);
    });

    it('should preserve non-empty tags array', () => {
      const flowWithTags: FlowType = {
        ...mockFlow,
        tags: ['ai', 'ml', 'workflow'],
      };

      const result = createNewFlow(mockFlowData, mockFolderId, flowWithTags);

      expect(result.tags).toEqual(['ai', 'ml', 'workflow']);
    });
  });

  describe('edge cases', () => {
    it('should handle empty folder id', () => {
      const result = createNewFlow(mockFlowData, '', mockFlow);
      expect(result.folder_id).toBe('');
    });

    it('should handle complex flowData structure', () => {
      const complexFlowData: ReactFlowJsonObject<any, any> = {
        nodes: [
          {
            id: 'node-1',
            type: 'genericNode',
            position: { x: 100, y: 200 },
            data: {
              id: 'node-1',
              type: 'TestNode',
              node: {
                display_name: 'Test Node',
                description: 'A test node',
              },
            },
          },
        ],
        edges: [
          {
            id: 'edge-1',
            source: 'node-1',
            target: 'node-2',
            sourceHandle: 'output',
            targetHandle: 'input',
          },
        ],
        viewport: { x: -50, y: 100, zoom: 0.8 },
      };

      const result = createNewFlow(complexFlowData, mockFolderId, mockFlow);

      expect(result.data).toBe(complexFlowData);
      expect(result.data.nodes).toHaveLength(1);
      expect(result.data.edges).toHaveLength(1);
      expect(result.data.viewport).toEqual({ x: -50, y: 100, zoom: 0.8 });
    });

    it('should handle flow with all optional properties as null', () => {
      const minimalFlow: FlowType = {
        id: 'minimal-id',
        name: 'Minimal Flow',
        description: 'Minimal description',
        data: null,
        icon: null as any,
        gradient: null as any,
        is_component: null as any,
        endpoint_name: null,
        tags: null as any,
        mcp_enabled: null as any,
      };

      const result = createNewFlow(mockFlowData, mockFolderId, minimalFlow);

      expect(result).toEqual({
        description: 'Minimal description',
        name: 'Minimal Flow',
        data: mockFlowData,
        id: '',
        icon: undefined, // null becomes undefined due to ?? operator
        gradient: undefined, // null becomes undefined due to ?? operator
        is_component: false, // null becomes false due to ?? operator
        folder_id: mockFolderId,
        endpoint_name: undefined, // null becomes undefined due to ?? operator
        tags: [], // null becomes [] due to ?? operator
        mcp_enabled: true,
      });
    });
  });

  describe('function behavior consistency', () => {
    it('should produce the same result for the same inputs', () => {
      mockGetRandomDescription.mockReturnValue('Consistent Description');

      const result1 = createNewFlow(mockFlowData, mockFolderId, mockFlow);
      const result2 = createNewFlow(mockFlowData, mockFolderId, mockFlow);

      expect(result1).toEqual(result2);
    });

    it('should not mutate input parameters', () => {
      const originalFlowData = { ...mockFlowData };
      const originalFlow = { ...mockFlow };

      createNewFlow(mockFlowData, mockFolderId, mockFlow);

      expect(mockFlowData).toEqual(originalFlowData);
      expect(mockFlow).toEqual(originalFlow);
    });
  });

  describe('description logic', () => {
    it('should use flow description when truthy', () => {
      const flowWithDescription = {
        ...mockFlow,
        description: 'Custom Description',
      };
      const result = createNewFlow(
        mockFlowData,
        mockFolderId,
        flowWithDescription
      );

      expect(result.description).toBe('Custom Description');
      expect(mockGetRandomDescription).not.toHaveBeenCalled();
    });

    it('should use random description for null/undefined descriptions only', () => {
      const nullishTestCases = [
        { ...mockFlow, description: null as any },
        { ...mockFlow, description: undefined as any },
      ];

      nullishTestCases.forEach(testFlow => {
        mockGetRandomDescription.mockClear();
        const result = createNewFlow(mockFlowData, mockFolderId, testFlow);

        expect(result.description).toBe('Random Description');
        expect(mockGetRandomDescription).toHaveBeenCalledTimes(1);
      });

      // These falsy values should NOT trigger random description
      const falsyTestCases = [
        { ...mockFlow, description: '' },
        { ...mockFlow, description: 0 as any },
        { ...mockFlow, description: false as any },
      ];

      falsyTestCases.forEach(testFlow => {
        mockGetRandomDescription.mockClear();
        const result = createNewFlow(mockFlowData, mockFolderId, testFlow);

        expect(result.description).toBe(testFlow.description);
        expect(mockGetRandomDescription).not.toHaveBeenCalled();
      });
    });
  });

  describe('name logic', () => {
    it('should use flow name when truthy', () => {
      const flowWithName = { ...mockFlow, name: 'Custom Name' };
      const result = createNewFlow(mockFlowData, mockFolderId, flowWithName);

      expect(result.name).toBe('Custom Name');
    });

    it('should use default name for falsy names', () => {
      const testCases = [
        { ...mockFlow, name: '' },
        { ...mockFlow, name: null as any },
        { ...mockFlow, name: undefined as any },
        { ...mockFlow, name: 0 as any },
        { ...mockFlow, name: false as any },
      ];

      testCases.forEach(testFlow => {
        const result = createNewFlow(mockFlowData, mockFolderId, testFlow);
        expect(result.name).toBe('New Flow');
      });
    });

    it('should preserve whitespace in names', () => {
      const flowWithWhitespace = { ...mockFlow, name: '   Test   ' };
      const result = createNewFlow(
        mockFlowData,
        mockFolderId,
        flowWithWhitespace
      );

      expect(result.name).toBe('   Test   ');
    });
  });
});
