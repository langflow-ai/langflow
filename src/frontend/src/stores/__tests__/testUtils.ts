import { act } from "@testing-library/react";

/**
 * Common test utilities for Zustand store tests
 */

/**
 * Creates a localStorage mock for testing
 */
export const createLocalStorageMock = () => {
  const mockStorage = {
    store: {} as { [key: string]: string },
    getItem: jest.fn((key: string) => mockStorage.store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      mockStorage.store[key] = value;
    }),
    removeItem: jest.fn((key: string) => {
      delete mockStorage.store[key];
    }),
    clear: jest.fn(() => {
      mockStorage.store = {};
    }),
    length: 0,
    key: jest.fn(() => null),
  };

  return mockStorage;
};

/**
 * Reset store state utility
 * Usage: resetStoreState(useMyStore, { prop1: value1, prop2: value2 })
 */
export const resetStoreState = <T>(
  store: { setState: (state: Partial<T>) => void },
  initialState: Partial<T>,
) => {
  act(() => {
    store.setState(initialState);
  });
};

/**
 * Common constants mock for tests that need @/constants/constants
 */
export const mockConstants = {
  OPENAI_VOICES: [
    { name: "Alloy", value: "alloy" },
    { name: "Echo", value: "echo" },
    { name: "Fable", value: "fable" },
  ],
  USER_PROJECTS_HEADER: "My Collection",
  STORE_USER_PROJECTS: "store_user_projects",
};

/**
 * Common API response patterns for mocking
 */
export const createMockApiResponse = <T>(data: T, status = 200) => ({
  data,
  status,
  statusText: "OK",
  headers: {},
  config: {},
});

/**
 * Creates a mock fetch function for API testing
 */
export const createMockFetch = (
  responses: Array<{ url?: string; response: any; status?: number }>,
) => {
  let callIndex = 0;

  return jest.fn((url: string) => {
    const mockResponse =
      responses[callIndex] || responses[responses.length - 1];
    callIndex++;

    return Promise.resolve({
      ok:
        (mockResponse.status || 200) >= 200 &&
        (mockResponse.status || 200) < 300,
      status: mockResponse.status || 200,
      json: () => Promise.resolve(mockResponse.response),
      text: () => Promise.resolve(JSON.stringify(mockResponse.response)),
    });
  });
};

/**
 * Common mock data factories
 */
export const mockDataFactory = {
  createUser: (overrides: Partial<any> = {}) => ({
    id: "user-1",
    username: "testuser",
    email: "test@example.com",
    is_active: true,
    is_superuser: false,
    created_at: "2023-01-01T00:00:00Z",
    updated_at: "2023-01-01T00:00:00Z",
    ...overrides,
  }),

  createFlow: (overrides: Partial<any> = {}) => ({
    id: "flow-1",
    name: "Test Flow",
    description: "A test flow",
    data: { nodes: [], edges: [] },
    is_component: false,
    updated_at: "2023-01-01T00:00:00Z",
    folder_id: null,
    endpoint_name: null,
    ...overrides,
  }),

  createFolder: (overrides: Partial<any> = {}) => ({
    id: "folder-1",
    name: "Test Folder",
    description: "A test folder",
    parent_id: null,
    created_at: "2023-01-01T00:00:00Z",
    updated_at: "2023-01-01T00:00:00Z",
    components_count: 0,
    flows_count: 0,
    ...overrides,
  }),

  createMessage: (overrides: Partial<any> = {}) => ({
    id: "message-1",
    text: "Test message",
    sender: "User",
    sender_name: "Test User",
    session_id: "session-1",
    timestamp: "2023-01-01T00:00:00Z",
    files: [],
    edit: false,
    thought: "",
    ...overrides,
  }),

  createVoice: (overrides: Partial<any> = {}) => ({
    name: "Test Voice",
    voice_id: "voice-1",
    ...overrides,
  }),

  createProvider: (overrides: Partial<any> = {}) => ({
    name: "Test Provider",
    value: "test-provider",
    ...overrides,
  }),

  createTag: (overrides: Partial<any> = {}) => ({
    id: "tag-1",
    name: "Test Tag",
    description: "A test tag",
    color: "#FF0000",
    ...overrides,
  }),

  createPagination: (overrides: Partial<any> = {}) => ({
    page: 1,
    size: 10,
    ...overrides,
  }),
};

/**
 * Common test assertions helpers
 */
export const testHelpers = {
  /**
   * Tests that a function toggles an array item correctly
   */
  testArrayToggle: <T>(
    initialArray: T[],
    item: T,
    toggleFn: (item: T) => void,
    getArray: () => T[],
  ) => {
    // Add item
    act(() => {
      toggleFn(item);
    });

    if (initialArray.includes(item)) {
      expect(getArray()).not.toContain(item);
    } else {
      expect(getArray()).toContain(item);
    }
  },

  /**
   * Tests multiple state updates in sequence
   */
  testSequentialUpdates: <T>(
    updates: Array<{ fn: () => void; expected: T }>,
    getter: () => T,
  ) => {
    updates.forEach(({ fn, expected }) => {
      act(() => {
        fn();
      });
      expect(getter()).toEqual(expected);
    });
  },
};

/**
 * Jest mock helpers
 */
export const mockHelpers = {
  /**
   * Creates a comprehensive localStorage mock and assigns it to global
   */
  setupLocalStorage: () => {
    const mockStorage = createLocalStorageMock();
    Object.defineProperty(window, "localStorage", {
      value: mockStorage,
      writable: true,
    });
    return mockStorage;
  },

  /**
   * Creates mock for @/constants/constants
   */
  mockConstants: () => {
    jest.mock("@/constants/constants", () => mockConstants);
  },

  /**
   * Creates mock for various API functions
   */
  mockApiCalls: () => {
    const mockApi = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      patch: jest.fn(),
    };
    return mockApi;
  },
};
