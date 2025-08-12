import { fireEvent, render, screen } from '@testing-library/react';
import CanvasControls from '../index';

// Capture flow functions for assertions
const reactFlowFns = {
  fitView: jest.fn(),
  zoomIn: jest.fn(),
  zoomOut: jest.fn(),
  zoomTo: jest.fn(),
};

// Mocks for external dependencies used internally
jest.mock('@xyflow/react', () => ({
  Panel: ({ children, ...props }: any) => <div data-testid="panel" {...props}>{children}</div>,
  useReactFlow: () => reactFlowFns,
  useStore: (_selector: any) => ({
    isInteractive: true,
    minZoomReached: false,
    maxZoomReached: false,
    zoom: 1,
  }),
  useStoreApi: () => ({ setState: jest.fn() }),
}));

jest.mock('@/stores/flowStore', () => ({
  __esModule: true,
  default: jest.fn(() => false),
}));

jest.mock('@/components/ui/separator', () => ({
  Separator: ({ orientation }: { orientation: 'vertical' | 'horizontal' }) => (
    <div data-testid={`separator-${orientation}`} />
  ),
}));

// Mock dropdowns to a simple render that exposes props for assertions
jest.mock('../dropdowns', () => ({
  CanvasControlsDropdown: (props: any) => (
    <div data-testid="controls-dropdown" {...props} />
  ),
  HelpDropdown: (props: any) => (
    <div data-testid="help-dropdown" {...props} />
  ),
}));

describe('CanvasControls', () => {
  it('renders panel and separators when children present', () => {
    render(<CanvasControls><div>child</div></CanvasControls>);
    expect(screen.getByTestId('main_canvas_controls')).toBeInTheDocument();
    const seps = screen.getAllByTestId('separator-vertical');
    expect(seps.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('controls-dropdown')).toBeInTheDocument();
    expect(screen.getByTestId('help-dropdown')).toBeInTheDocument();
  });

  it('handles keyboard shortcuts with meta/ctrl keys', () => {
    render(<CanvasControls />);
    reactFlowFns.fitView.mockClear();
    reactFlowFns.zoomIn.mockClear();
    reactFlowFns.zoomOut.mockClear();
    reactFlowFns.zoomTo.mockClear();

    // Press + (Equal) with meta
    fireEvent.keyDown(document, { key: '+', code: 'Equal', metaKey: true });
    // Press - (Minus) with ctrl
    fireEvent.keyDown(document, { key: '-', code: 'Minus', ctrlKey: true });
    // Press 1 (Digit1) with meta
    fireEvent.keyDown(document, { key: '1', code: 'Digit1', metaKey: true });
    // Press 0 (Digit0) with ctrl
    fireEvent.keyDown(document, { key: '0', code: 'Digit0', ctrlKey: true });

    expect(reactFlowFns.zoomIn).toHaveBeenCalled();
    expect(reactFlowFns.zoomOut).toHaveBeenCalled();
    expect(reactFlowFns.fitView).toHaveBeenCalled();
    expect(reactFlowFns.zoomTo).toHaveBeenCalledWith(1);
  });
});


