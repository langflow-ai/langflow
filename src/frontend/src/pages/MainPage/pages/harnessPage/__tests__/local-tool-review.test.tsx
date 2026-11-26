import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { LocalToolBinding } from "@/pages/MainPage/entities";
import { LocalToolReview } from "../components/local-tool-review";

const original: LocalToolBinding = {
  flow_id: "tool",
  name: "Research tool",
  revision: "a".repeat(64),
  version_id: "original-snapshot",
  dependencies: [
    {
      flow_id: "child",
      name: "Source rules",
      revision: "b".repeat(64),
      version_id: "child-snapshot",
    },
  ],
};
let mockChoices: LocalToolBinding[];
let mockError = false;
const mockRefetch = jest.fn();
jest.mock(
  "@/controllers/API/queries/folders/use-local-tool-definitions",
  () => ({
    useLocalToolDefinitions: () => ({
      data: mockChoices,
      isLoading: false,
      isError: mockError,
      refetch: mockRefetch,
    }),
  }),
);
const onChange = jest.fn();
const onOpen = jest.fn();
const show = (disabled = false) =>
  render(
    <MemoryRouter>
      <LocalToolReview
        projectId="harness"
        selected={["tool"]}
        value={{ tool: original }}
        saved={{ tool: original }}
        disabled={disabled}
        onChange={onChange}
        onOpen={onOpen}
      />
    </MemoryRouter>,
  );

beforeEach(() => {
  jest.clearAllMocks();
  mockError = false;
  mockChoices = [JSON.parse(JSON.stringify(original))];
});

it("reviews a changed child without mutating the saved binding", () => {
  mockChoices[0].version_id = undefined;
  mockChoices[0].dependencies = [
    { flow_id: "child", name: "Source rules", revision: "c".repeat(64) },
  ];
  show();
  expect(screen.getByText("Changed since review")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /update binding/i }));
  expect(onChange).toHaveBeenCalledWith({ tool: mockChoices[0] });
  expect(original.dependencies?.[0].revision).toBe("b".repeat(64));
  fireEvent.click(screen.getByText(/Research tool ·/));
  const link = screen.getByRole("link", { name: "Source rules" });
  expect(link).toHaveAttribute("href", "/flow/child");
  fireEvent.click(link);
  expect(onOpen).toHaveBeenCalledTimes(1);
});

it("treats renamed tools as changes even when the root code revision matches", () => {
  mockChoices[0].name = "Renamed research tool";
  show();
  expect(
    screen.getByRole("button", { name: /update binding/i }),
  ).toBeInTheDocument();
});

it("does not request another review solely because snapshot IDs differ", () => {
  mockChoices[0].version_id = undefined;
  mockChoices[0].dependencies![0].version_id = undefined;
  show();
  expect(screen.getByText("Matches the reviewed revision")).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /update binding/i }),
  ).not.toBeInTheDocument();
});

it("retains the reviewed definition when the current tool is unavailable", () => {
  mockChoices = [];
  show();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Selected output unavailable",
  );
  fireEvent.click(screen.getByText(/Research tool ·/));
  expect(screen.getByText("original-snapshot")).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /update binding/i }),
  ).not.toBeInTheDocument();
});

it("prevents review changes during a save and allows retry after a read failure", () => {
  mockChoices[0].description = "Changed description";
  const view = show(true);
  expect(
    screen.getByRole("button", { name: /update binding/i }),
  ).toBeDisabled();
  view.unmount();
  mockError = true;
  show();
  fireEvent.click(screen.getByRole("button", { name: /retry/i }));
  expect(mockRefetch).toHaveBeenCalledTimes(1);
});
