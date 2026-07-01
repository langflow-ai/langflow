import { render, screen } from "@testing-library/react";
import type { PlanNode } from "@/controllers/API/queries/lothal";

const mockCreateLink: {
  mutate: jest.Mock;
  isPending: boolean;
  isError: boolean;
  error: unknown;
} = { mutate: jest.fn(), isPending: false, isError: false, error: undefined };

jest.mock("@/controllers/API/queries/lothal", () => ({
  useCreatePlanLink: () => mockCreateLink,
}));

import { PlanGraph } from "../PlanGraph";

const node = (id: string, name: string, depth = 0): PlanNode => ({
  id,
  parent_id: null,
  kind: "story",
  state: "draft",
  name,
  depth,
});

const nodes = [node("a", "Alpha", 0), node("b", "Bravo", 1)];

beforeEach(() => {
  jest.clearAllMocks();
  mockCreateLink.isError = false;
  mockCreateLink.error = undefined;
  mockCreateLink.isPending = false;
});

describe("PlanGraph", () => {
  it("surfaces an add-link failure inline with the server reason", () => {
    mockCreateLink.isError = true;
    mockCreateLink.error = {
      response: { data: { detail: "would create a cycle" } },
    };
    render(
      <PlanGraph
        projectId="p1"
        nodes={nodes}
        links={[]}
        editable
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.getByText("Couldn't add the link")).toBeInTheDocument();
    expect(screen.getByText(/would create a cycle/)).toBeInTheDocument();
  });

  it("shows no error banner on the happy path", () => {
    render(
      <PlanGraph
        projectId="p1"
        nodes={nodes}
        links={[]}
        editable
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.queryByText("Couldn't add the link")).toBeNull();
  });
});
