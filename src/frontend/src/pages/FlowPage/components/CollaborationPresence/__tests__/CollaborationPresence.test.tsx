import { render, screen } from "@testing-library/react";

jest.mock("react-i18next", () => {
  const actual =
    jest.requireActual<typeof import("react-i18next")>("react-i18next");
  return {
    ...actual,
    useTranslation: () => ({
      t: (
        key: string,
        opts?: { defaultValue?: string; label?: string; count?: number },
      ) => {
        if (!opts?.defaultValue) {
          return key;
        }
        return Object.entries(opts).reduce((text, [optionKey, value]) => {
          if (optionKey === "defaultValue" || value == null) {
            return text;
          }
          return text.replace(
            new RegExp(`\\{\\{${optionKey}\\}\\}`, "g"),
            String(value),
          );
        }, opts.defaultValue);
      },
      i18n: { language: "en" },
    }),
  };
});

import CollaborationPresenceAvatars from "../index";

describe("CollaborationPresenceAvatars", () => {
  it("renders a compact avatar stack for collaborators", () => {
    render(
      <CollaborationPresenceAvatars
        connectionStatus="ready"
        collaborators={[
          {
            user_id: "user-1",
            username: "ana",
            profile_image: null,
            selected: null,
            selectionLabel: null,
            isCurrentUser: true,
            color: "#3b82f6",
          },
          {
            user_id: "user-2",
            username: "bob",
            profile_image: null,
            selected: { kind: "node", id: "node-1" },
            selectionLabel: "Parser",
            isCurrentUser: false,
            color: "#f97316",
          },
        ]}
      />,
    );

    expect(screen.getByTestId("collaboration-presence")).toBeInTheDocument();
    const currentUserAvatar = screen.getByTestId(
      "collaboration-presence-user-user-1",
    );
    const otherUserAvatar = screen.getByTestId(
      "collaboration-presence-user-user-2",
    );

    expect(currentUserAvatar).toBeInTheDocument();
    expect(otherUserAvatar).toBeInTheDocument();
    expect(currentUserAvatar).toHaveStyle({ borderColor: "#3b82f6" });
    expect(otherUserAvatar).toHaveStyle({ borderColor: "#f97316" });
    expect(
      screen.queryByTestId("collaboration-presence-row-user-1"),
    ).not.toBeInTheDocument();
  });

  it("shows a status indicator while the connection is not ready", () => {
    render(
      <CollaborationPresenceAvatars
        collaborators={[
          {
            user_id: "user-1",
            username: "ana",
            profile_image: null,
            selected: null,
            selectionLabel: null,
            isCurrentUser: true,
            color: "#3b82f6",
          },
        ]}
        connectionStatus="connecting"
      />,
    );

    expect(
      screen.getByTestId("collaboration-presence-status"),
    ).toBeInTheDocument();
  });
});
