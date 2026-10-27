import { render, screen } from "@testing-library/react";
import TriggersListState from "../components/TriggersListState";

it("keeps a loaded table mounted after a failed background poll", () => {
  render(
    <TriggersListState
      query={{
        isLoading: false,
        isError: true,
        error: new Error("Offline"),
        data: [{}],
      }}
      total={1}
      visible={1}
      emptyKey="triggers.empty.mine"
    >
      <div>Loaded trigger</div>
    </TriggersListState>,
  );
  expect(screen.getByText("Loaded trigger")).toBeInTheDocument();
});
