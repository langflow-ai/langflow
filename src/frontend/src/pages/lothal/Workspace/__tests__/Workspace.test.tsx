import { render, screen } from "@testing-library/react";
import React from "react";

// jsdom has no scrollIntoView; the chat panel calls it on every message change.
Element.prototype.scrollIntoView = jest.fn();

const mockNavigate = jest.fn();
let mockParams: { projectId?: string } = { projectId: "p1" };
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => mockParams,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/pages/FlowPage/consts", () => ({ nodeTypes: {} }));

jest.mock("@xyflow/react", () => ({
  __esModule: true,
  ReactFlow: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="reactflow">{children}</div>
  ),
  Background: () => <div data-testid="background" />,
  Controls: () => <div data-testid="controls" />,
  ReactFlowProvider: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
  useNodesState: () => [[], jest.fn(), jest.fn()],
  useEdgesState: () => [[], jest.fn(), jest.fn()],
}));

const mockUseProjects = jest.fn();
const mockUseMessages = jest.fn();
const mockSendMutate = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useProjects: () => mockUseProjects(),
  useMessages: () => mockUseMessages(),
  useSendMessage: () => ({ mutateAsync: mockSendMutate }),
}));

import Workspace from "../index";

describe("Lothal Workspace", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockParams = { projectId: "p1" };
    mockUseMessages.mockReturnValue({ data: [] });
  });

  it("shows Loading… while the projects query is loading", () => {
    mockUseProjects.mockReturnValue({ data: undefined, isLoading: true });
    render(<Workspace />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows Project not found. once loaded with no matching id", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Workspace />);
    expect(screen.getByText("Project not found.")).toBeInTheDocument();
  });

  it("renders the workspace shell when the project exists", () => {
    mockUseProjects.mockReturnValue({
      data: [{ id: "p1", name: "Demo", phase: "CLARIFICATION" }],
      isLoading: false,
    });
    render(<Workspace />);
    expect(screen.getByText("Demo")).toBeInTheDocument();
    expect(screen.getByText("Clarifying")).toBeInTheDocument();
    expect(screen.getByTestId("reactflow")).toBeInTheDocument();
  });
});
