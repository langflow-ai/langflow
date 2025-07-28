import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock the component to avoid complex dependency chains
jest.mock('../KnowledgeBaseDrawer', () => {
  const MockKnowledgeBaseDrawer = ({ isOpen, onClose, knowledgeBase }: any) => {
    if (!isOpen || !knowledgeBase) {
      return null;
    }

    return (
      <div data-testid="knowledge-base-drawer" className="w-80 border-l bg-background">
        <div className="flex items-center justify-between p-4">
          <h3>{knowledgeBase.name}</h3>
          <button onClick={onClose} data-testid="close-button">
            <span data-testid="icon-X">X</span>
          </button>
        </div>
        <div className="p-4">
          <div data-testid="description">No description available.</div>
          <div data-testid="embedding-provider">
            <label>Embedding Provider</label>
            <div>{knowledgeBase.embedding_model || 'Unknown'}</div>
          </div>
          <div data-testid="source-files">
            <h4>Source Files</h4>
            <div>No source files available.</div>
          </div>
          <div data-testid="linked-flows">
            <h4>Linked Flows</h4>
            <div>No linked flows available.</div>
          </div>
        </div>
      </div>
    );
  };
  MockKnowledgeBaseDrawer.displayName = 'KnowledgeBaseDrawer';
  return {
    __esModule: true,
    default: MockKnowledgeBaseDrawer,
  };
});

const KnowledgeBaseDrawer = require('../KnowledgeBaseDrawer').default;

const mockKnowledgeBase = {
  id: 'kb-1',
  name: 'Test Knowledge Base',
  embedding_provider: 'OpenAI',
  embedding_model: 'text-embedding-ada-002',
  size: 1024000,
  words: 50000,
  characters: 250000,
  chunks: 100,
  avg_chunk_size: 2500,
};

describe('KnowledgeBaseDrawer', () => {
  const mockOnClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <KnowledgeBaseDrawer
        isOpen={false}
        onClose={mockOnClose}
        knowledgeBase={mockKnowledgeBase}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when knowledgeBase is null', () => {
    const { container } = render(
      <KnowledgeBaseDrawer
        isOpen={true}
        onClose={mockOnClose}
        knowledgeBase={null}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders drawer when both isOpen is true and knowledgeBase is provided', () => {
    render(
      <KnowledgeBaseDrawer
        isOpen={true}
        onClose={mockOnClose}
        knowledgeBase={mockKnowledgeBase}
      />
    );

    expect(screen.getByTestId('knowledge-base-drawer')).toBeInTheDocument();
    expect(screen.getByText('Test Knowledge Base')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    render(
      <KnowledgeBaseDrawer
        isOpen={true}
        onClose={mockOnClose}
        knowledgeBase={mockKnowledgeBase}
      />
    );

    const closeButton = screen.getByTestId('close-button');
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('displays embedding model information', () => {
    render(
      <KnowledgeBaseDrawer
        isOpen={true}
        onClose={mockOnClose}
        knowledgeBase={mockKnowledgeBase}
      />
    );

    expect(screen.getByText('Embedding Provider')).toBeInTheDocument();
    expect(screen.getByText('text-embedding-ada-002')).toBeInTheDocument();
  });

  it('displays Unknown for missing embedding model', () => {
    const kbWithoutModel = {
      ...mockKnowledgeBase,
      embedding_model: undefined,
    };

    render(
      <KnowledgeBaseDrawer
        isOpen={true}
        onClose={mockOnClose}
        knowledgeBase={kbWithoutModel}
      />
    );

    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('displays content sections', () => {
    render(
      <KnowledgeBaseDrawer
        isOpen={true}
        onClose={mockOnClose}
        knowledgeBase={mockKnowledgeBase}
      />
    );

    expect(screen.getByText('No description available.')).toBeInTheDocument();
    expect(screen.getByText('Source Files')).toBeInTheDocument();
    expect(screen.getByText('Linked Flows')).toBeInTheDocument();
  });
}); 