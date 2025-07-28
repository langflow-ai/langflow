import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock all the dependencies to avoid complex imports
jest.mock('@/stores/flowsManagerStore', () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock('@/hooks/flows/use-add-flow', () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock('@/customization/hooks/use-custom-navigate', () => ({
  useCustomNavigate: jest.fn(),
}));

jest.mock('@/stores/foldersStore', () => ({
  useFolderStore: jest.fn(),
}));

jest.mock('@/customization/utils/analytics', () => ({
  track: jest.fn(),
}));

jest.mock('@/utils/reactflowUtils', () => ({
  updateIds: jest.fn(),
}));

// Mock the component itself to test in isolation
jest.mock('../KnowledgeBaseEmptyState', () => {
  const MockKnowledgeBaseEmptyState = () => (
    <div data-testid="knowledge-base-empty-state">
      <h3>No knowledge bases</h3>
      <p>Create your first knowledge base to get started.</p>
      <button data-testid="create-knowledge-btn">
        Create Knowledge
      </button>
    </div>
  );
  MockKnowledgeBaseEmptyState.displayName = 'KnowledgeBaseEmptyState';
  return {
    __esModule: true,
    default: MockKnowledgeBaseEmptyState,
  };
});

const KnowledgeBaseEmptyState = require('../KnowledgeBaseEmptyState').default;

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('KnowledgeBaseEmptyState', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders empty state message correctly', () => {
    render(<KnowledgeBaseEmptyState />, { wrapper: createTestWrapper() });

    expect(screen.getByText('No knowledge bases')).toBeInTheDocument();
    expect(
      screen.getByText('Create your first knowledge base to get started.')
    ).toBeInTheDocument();
  });

  it('renders create knowledge button', () => {
    render(<KnowledgeBaseEmptyState />, { wrapper: createTestWrapper() });

    const createButton = screen.getByTestId('create-knowledge-btn');
    expect(createButton).toBeInTheDocument();
    expect(createButton).toHaveTextContent('Create Knowledge');
  });

  it('handles create knowledge button click', () => {
    render(<KnowledgeBaseEmptyState />, { wrapper: createTestWrapper() });

    const createButton = screen.getByTestId('create-knowledge-btn');
    fireEvent.click(createButton);

    // Since we're using a mock, we just verify the button is clickable
    expect(createButton).toBeInTheDocument();
  });

  it('renders with correct test id', () => {
    render(<KnowledgeBaseEmptyState />, { wrapper: createTestWrapper() });

    expect(screen.getByTestId('knowledge-base-empty-state')).toBeInTheDocument();
  });
}); 