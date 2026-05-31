import { render, screen } from "@testing-library/react";

import CollaborationPresence from "../index";

describe("CollaborationPresence", () => {
  it("renders other collaborators and hides the current user", () => {
    render(
      <CollaborationPresence
        currentUserId="user-1"
        users={[
          { user_id: "user-1", username: "ana" },
          { user_id: "user-2", username: "bob", profile_image: null },
        ]}
      />,
    );

    expect(screen.getByTestId("collaboration-presence")).toBeInTheDocument();
    expect(
      screen.getByTestId("collaboration-presence-user-user-2"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("collaboration-presence-user-user-1"),
    ).not.toBeInTheDocument();
  });

  it("renders nothing when only the current user is present", () => {
    const { container } = render(
      <CollaborationPresence
        currentUserId="user-1"
        users={[{ user_id: "user-1", username: "ana" }]}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
