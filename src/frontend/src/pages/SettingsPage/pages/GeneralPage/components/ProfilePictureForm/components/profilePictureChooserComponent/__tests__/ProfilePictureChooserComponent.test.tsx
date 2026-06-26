import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

jest.mock("react-i18next", () => ({
  __esModule: true,
  useTranslation: () => ({
    t: (key: string, optsOrFallback?: Record<string, unknown> | string) => {
      if (
        key === "settings.avatarAlt" &&
        optsOrFallback &&
        typeof optsOrFallback === "object"
      ) {
        return `${optsOrFallback.folder} avatar ${optsOrFallback.index}`;
      }
      if (key.startsWith("settings.profilePictureCategory.")) {
        return key.split(".").at(-1) ?? key;
      }
      return key;
    },
  }),
  initReactI18next: {
    type: "3rdParty",
    init: () => {},
  },
}));

jest.mock("@/customization/utils/custom-pre-load-image-url", () => ({
  customPreLoadImageUrl: (path: string) =>
    `/api/v1/files/profile_pictures/${path}`,
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (selector: (s: { dark: boolean }) => unknown) =>
    selector({ dark: false }),
}));

jest.mock("../hooks/use-preload-images", () => {
  const { useEffect } = require("react");
  return {
    __esModule: true,
    default: (setImagesLoaded: (v: boolean) => void) => {
      useEffect(() => {
        setImagesLoaded(true);
      }, []);
    },
  };
});

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div data-testid="loading-spinner" />,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    unstyled: _unstyled,
    ...rest
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    unstyled?: boolean;
    children: React.ReactNode;
  }) => (
    <button onClick={onClick} {...rest}>
      {children}
    </button>
  ),
}));

import ProfilePictureChooserComponent from "../index";

const PROFILE_PICTURES = {
  files: [],
  People: ["avatar-01.svg", "avatar-02.svg"],
  Space: ["space-01.svg"],
};

describe("ProfilePictureChooserComponent", () => {
  it("shows loading spinner when loading prop is true", () => {
    render(
      <ProfilePictureChooserComponent
        loading={true}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={jest.fn()}
      />,
    );
    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders images with src URLs built from customPreLoadImageUrl", async () => {
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={jest.fn()}
      />,
    );
    const peopleBtn = await screen.findByRole("button", {
      name: "People avatar 1",
    });
    expect(peopleBtn.querySelector("img")).toHaveAttribute(
      "src",
      "/api/v1/files/profile_pictures/People/avatar-01.svg",
    );
    const spaceBtn = screen.getByRole("button", { name: "Space avatar 1" });
    expect(spaceBtn.querySelector("img")).toHaveAttribute(
      "src",
      "/api/v1/files/profile_pictures/Space/space-01.svg",
    );
  });

  it("renders folder category labels when loaded", async () => {
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={jest.fn()}
      />,
    );
    await screen.findByText("People");
    expect(screen.getByText("Space")).toBeInTheDocument();
  });

  it("renders one button per avatar path", async () => {
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={jest.fn()}
      />,
    );
    const buttons = await screen.findAllByRole("button");
    // 2 People + 1 Space = 3
    expect(buttons).toHaveLength(3);
  });

  it("buttons expose accessible names derived from the category and position", async () => {
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={jest.fn()}
      />,
    );
    expect(
      await screen.findByRole("button", { name: "People avatar 1" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "People avatar 2" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Space avatar 1" }),
    ).toBeInTheDocument();
  });

  it("selected button has aria-pressed=true, others have aria-pressed=false", async () => {
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={PROFILE_PICTURES}
        value="People/avatar-01.svg"
        onChange={jest.fn()}
      />,
    );
    const buttons = await screen.findAllByRole("button");
    expect(buttons[0]).toHaveAttribute("aria-pressed", "true");
    expect(buttons[1]).toHaveAttribute("aria-pressed", "false");
    expect(buttons[2]).toHaveAttribute("aria-pressed", "false");
  });

  it("all buttons have aria-pressed=false when no value is selected", async () => {
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={jest.fn()}
      />,
    );
    const buttons = await screen.findAllByRole("button");
    buttons.forEach((btn) => {
      expect(btn).toHaveAttribute("aria-pressed", "false");
    });
  });

  it("calls onChange with the correct folder/path key when clicked", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={onChange}
      />,
    );
    const buttons = await screen.findAllByRole("button");
    await user.click(buttons[1]);
    expect(onChange).toHaveBeenCalledWith("People/avatar-02.svg");
  });

  it("calls onChange once per click", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={onChange}
      />,
    );
    const buttons = await screen.findAllByRole("button");
    await user.click(buttons[0]);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("does not render buttons when profilePictures is empty", async () => {
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={{ files: [] }}
        value=""
        onChange={jest.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
  });

  it("renders buttons from all folders when multiple folders are present", async () => {
    const multiFolder = {
      files: [],
      People: ["a.svg", "b.svg", "c.svg"],
      Space: ["x.svg", "y.svg"],
    };
    render(
      <ProfilePictureChooserComponent
        loading={false}
        profilePictures={multiFolder}
        value=""
        onChange={jest.fn()}
      />,
    );
    const buttons = await screen.findAllByRole("button");
    expect(buttons).toHaveLength(5);
  });

  it("does not show buttons while loading even when profilePictures is provided", () => {
    render(
      <ProfilePictureChooserComponent
        loading={true}
        profilePictures={PROFILE_PICTURES}
        value=""
        onChange={jest.fn()}
      />,
    );
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});
