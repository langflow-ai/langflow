// Jest setup file to mock globals and Vite-specific syntax

// Mock import.meta
global.import = {
  meta: {
    env: {
      CI: process.env.CI || false,
      NODE_ENV: 'test',
      MODE: 'test',
      DEV: false,
      PROD: false,
      VITE_API_URL: 'http://localhost:7860',
    },
  },
};

// Mock crypto for Node.js environment
if (typeof global.crypto === 'undefined') {
  const { webcrypto } = require('crypto');
  global.crypto = webcrypto;
}

// Mock URL if not available
if (typeof global.URL === 'undefined') {
  global.URL = require('url').URL;
}

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;

// Mock sessionStorage
global.sessionStorage = localStorageMock; 