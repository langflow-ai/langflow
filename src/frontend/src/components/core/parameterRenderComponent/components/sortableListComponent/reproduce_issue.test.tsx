import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import * as ReactSortableModule from "react-sortablejs";
import SortableListComponent from "./index";

// Mock ListSelectionComponent to avoid its complexity
jest.mock("@/CustomNodes/GenericNode/components/ListSelectionComponent", () => {
  return function MockListSelectionComponent(props) {
    return (
      <div data-testid="list-selection-component">ListSelectionComponent</div>
    );
  };
});

// Mock genericIconComponent
jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon(props) {
    return <div data-testid={`icon-${props.name}`}>Icon</div>;
  };
});

// Mock ui components
jest.mock("@/components/ui/button", () => ({
  Button: (props) => <button {...props}>{props.children}</button>,
}));

describe("SortableListComponent reproduction", () => {
  it("should not trigger handleOnNewValue on initial render", async () => {
    const handleOnNewValue = jest.fn();
    const props = {
      tooltip: "",
      name: "test-list",
      value: [{ name: "item1" }, { name: "item2" }],
      handleOnNewValue: handleOnNewValue,
      disabled: false,
      recommended: false,
      placeholder: "Select items",
      isList: true,
      fileTypes: [],
      onDelete: jest.fn(),
      id: "test-id",
      limit: 10,
    };

    render(<SortableListComponent {...props} />);

    // Wait a tick to ensure effects run
    await waitFor(() => {}, { timeout: 0 });

    if (handleOnNewValue.mock.calls.length > 0) {
      console.log(
        "handleOnNewValue was called with:",
        handleOnNewValue.mock.calls[0][0],
      );
    }

    expect(handleOnNewValue).not.toHaveBeenCalled();
  });

  it("should mark preserved cloud-incompatible selections", () => {
    render(
      <SortableListComponent
        tooltip=""
        name="storage_location"
        value={[{ name: "Local" }]}
        handleOnNewValue={jest.fn()}
        disabled={false}
        recommended={false}
        placeholder="Select items"
        isList={true}
        fileTypes={[]}
        onDelete={jest.fn()}
        id="test-id"
        limit={1}
        cloudIncompatibleOptions={["Local"]}
      />,
    );

    expect(screen.getByText("Local")).toBeInTheDocument();
    expect(screen.getByText("Not available in cloud")).toBeInTheDocument();
  });
});
