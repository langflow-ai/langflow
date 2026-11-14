import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useUtilityStore } from "@/stores/utilityStore";
import EvalsRoute from "../EvalsRoute";

function openRunByAddress() {
  render(
    <MemoryRouter initialEntries={["/assets/evaluations/eval-1?run=run-1"]}>
      <Routes>
        <Route
          path="/assets/evaluations/:evaluationId"
          element={
            <EvalsRoute>
              <p>evaluation page</p>
            </EvalsRoute>
          }
        />
        <Route path="/flows" element={<p>flows page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("EvalsRoute", () => {
  afterEach(() => useUtilityStore.setState({ featureFlags: {} }));

  it("should wait for the server's flags instead of redirecting when the page is opened by its address", () => {
    useUtilityStore.setState({ featureFlags: {} });
    openRunByAddress();
    expect(screen.getByTestId("loading-icon")).toBeInTheDocument();
    expect(screen.queryByText("flows page")).not.toBeInTheDocument();
    expect(screen.queryByText("evaluation page")).not.toBeInTheDocument();
  });

  it("should show the page once the flag arrives as enabled", () => {
    useUtilityStore.setState({ featureFlags: {} });
    openRunByAddress();
    expect(screen.queryByText("evaluation page")).not.toBeInTheDocument();
    act(() => useUtilityStore.setState({ featureFlags: { evals: true } }));
    expect(screen.getByText("evaluation page")).toBeInTheDocument();
  });

  it("should redirect to the flows page when the server disables evals", () => {
    useUtilityStore.setState({ featureFlags: { evals: false } });
    openRunByAddress();
    expect(screen.getByText("flows page")).toBeInTheDocument();
  });
});
