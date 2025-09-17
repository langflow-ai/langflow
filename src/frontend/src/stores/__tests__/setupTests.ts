/**
 * Common test setup for Zustand store tests
 * This file contains shared mocks and configurations used across multiple test files
 */

// Mock crypto.getRandomValues for tests that use UUID generation
Object.defineProperty(global, "crypto", {
  value: {
    getRandomValues: (arr: any[]) => {
      for (let i = 0; i < arr.length; i++) {
        arr[i] = Math.floor(Math.random() * 256);
      }
      return arr;
    },
  },
});

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock IntersectionObserver
global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Common environment variable mocks
process.env.REACT_APP_BACKEND_URL = "http://localhost:7860";
process.env.NODE_ENV = "test";

// Mock document methods used in stores
Object.defineProperty(document, "querySelector", {
  value: jest.fn(() => null),
  writable: true,
});

Object.defineProperty(document, "getElementById", {
  value: jest.fn(() => null),
  writable: true,
});

// Mock window.location
Object.defineProperty(window, "location", {
  value: {
    href: "http://localhost:3000",
    origin: "http://localhost:3000",
    pathname: "/",
    search: "",
    hash: "",
    reload: jest.fn(),
    assign: jest.fn(),
  },
  writable: true,
});

// Clear all mocks before each test
beforeEach(() => {
  jest.clearAllMocks();
});
