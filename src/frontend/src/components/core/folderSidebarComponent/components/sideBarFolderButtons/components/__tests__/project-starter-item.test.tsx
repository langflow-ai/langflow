import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { MouseEvent, ReactNode } from "react";
import { api } from "@/controllers/API/api";
import { useFolderStore } from "@/stores/foldersStore";
import { ProjectStarterItem } from "../project-starter-item";

const mockNavigate = jest.fn();
const mockSetError = jest.fn();
jest.mock("@/controllers/API/api", () => ({ api: { post: jest.fn() } }));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (select) => select({ setErrorData: mockSetError }),
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenuItem: ({
    children,
    disabled,
    onSelect,
  }: {
    children: ReactNode;
    disabled: boolean;
    onSelect: (event: MouseEvent) => void;
  }) => (
    <button disabled={disabled} onClick={onSelect}>
      {children}
    </button>
  ),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) =>
      options?.defaultValue ?? key,
  }),
}));

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const invalidate = jest.spyOn(client, "invalidateQueries");
  const onCreated = jest.fn();
  render(
    <QueryClientProvider client={client}>
      <ProjectStarterItem
        starter={{
          name: "research",
          display_name: "Research agent",
          description: "A harness and a separate Tool Pack.",
        }}
        disabled={false}
        onCreated={onCreated}
      />
    </QueryClientProvider>,
  );
  return { onCreated, invalidate };
}

beforeEach(() => {
  jest.clearAllMocks();
  useFolderStore.getState().resetStore();
});

test("creates the composition once and opens its harness after creation", async () => {
  jest.mocked(api.post).mockResolvedValue({
    data: { id: "new-harness", project_type: "agent-harness" },
  });
  const { onCreated, invalidate } = setup();
  let existsBeforeNavigation = false;
  mockNavigate.mockImplementationOnce(() => {
    // HomePage resolves routes from this store. A missing newly-created project
    // redirects to /all even though its creation succeeded.
    existsBeforeNavigation = useFolderStore
      .getState()
      .folders.some((folder) => folder.id === "new-harness");
  });
  fireEvent.click(screen.getByRole("button", { name: /Research agent/ }));
  await waitFor(() =>
    expect(mockNavigate).toHaveBeenCalledWith(
      "/all/folder/new-harness?tab=harness",
    ),
  );
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(api.post).toHaveBeenCalledWith(
    expect.stringMatching(/\/projects\/starters\/research$/),
  );
  expect(onCreated).toHaveBeenCalledTimes(1);
  expect(existsBeforeNavigation).toBe(true);
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["useGetFolders"] });
});

test("keeps a failed creation visible without retrying or navigating", async () => {
  jest.mocked(api.post).mockRejectedValue({
    response: {
      status: 500,
      data: { detail: "Could not create the starter." },
    },
  });
  const { onCreated } = setup();
  fireEvent.click(screen.getByRole("button", { name: /Research agent/ }));
  await waitFor(() => expect(mockSetError).toHaveBeenCalled());
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(mockNavigate).not.toHaveBeenCalled();
  expect(onCreated).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: /Research agent/ })).toBeEnabled();
});
