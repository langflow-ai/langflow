import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { SidebarProvider, useSidebar } from "@/components/ui/sidebar";
import { useVersionHistoryLink } from "../useVersionHistoryLink";

let previousConsume: (() => void) | undefined;

function Destination({ flowId }: { flowId: string }) {
  const { requestedVersionId, consumeVersionLink } = useVersionHistoryLink(
    flowId,
    true,
  );
  const { open, activeSection, setOpen, setActiveSection } = useSidebar();
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="state">
        {JSON.stringify({
          open,
          activeSection,
          requestedVersionId,
          search: location.search,
        })}
      </output>
      <button onClick={consumeVersionLink}>Consume</button>
      <button
        onClick={() => {
          setActiveSection("components");
          setOpen(false);
        }}
      >
        Leave versions
      </button>
      <button
        onClick={() => {
          previousConsume = consumeVersionLink;
          navigate("/flow/flow-2?version=new-version&keep=value");
        }}
      >
        Navigate
      </button>
      <button onClick={() => previousConsume?.()}>Consume old request</button>
    </>
  );
}

function Harness({ flowId }: { flowId: string }) {
  return (
    <MemoryRouter
      initialEntries={["/flow/flow-1?version=recovery-1&keep=value"]}
    >
      <Routes>
        <Route
          path="/flow/:id"
          element={
            <SidebarProvider defaultOpen={false} defaultSection="components">
              <Destination flowId={flowId} />
            </SidebarProvider>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

const state = () => JSON.parse(screen.getByTestId("state").textContent!);

beforeEach(() => {
  document.cookie = "sidebar_state=; max-age=0";
  document.cookie = "sidebar:section=; max-age=0";
  previousConsume = undefined;
});

it("opens the exact version destination even when the sidebar was collapsed", () => {
  render(<Harness flowId="flow-1" />);

  expect(state()).toMatchObject({
    open: true,
    activeSection: "versions",
    requestedVersionId: "recovery-1",
  });
});

it("consumes only the version query and leaves later sidebar navigation alone", async () => {
  const user = userEvent.setup();
  render(<Harness flowId="flow-1" />);

  await user.click(screen.getByRole("button", { name: "Consume" }));
  await user.click(screen.getByRole("button", { name: "Leave versions" }));

  expect(state()).toMatchObject({
    open: false,
    activeSection: "components",
    search: "?keep=value",
  });
  expect(state().requestedVersionId).toBeUndefined();
});

it("waits for the requested flow before selecting a version", () => {
  const { rerender } = render(<Harness flowId="previous-flow" />);
  expect(state().requestedVersionId).toBeUndefined();
  expect(state().activeSection).toBe("components");

  rerender(<Harness flowId="flow-1" />);

  expect(state()).toMatchObject({
    open: true,
    activeSection: "versions",
    requestedVersionId: "recovery-1",
  });
});

it("does not consume a newer navigation through an old request callback", async () => {
  const user = userEvent.setup();
  render(<Harness flowId="flow-1" />);

  await user.click(screen.getByRole("button", { name: "Navigate" }));
  await user.click(screen.getByRole("button", { name: "Consume old request" }));

  expect(state().search).toBe("?version=new-version&keep=value");
});
