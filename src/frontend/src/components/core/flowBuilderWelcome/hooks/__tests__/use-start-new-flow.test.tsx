/**
 * Tests for the "New Flow" entry point: a second click while the first create
 * is in flight, or before the new route has committed, must not create a second
 * flow, and nothing may leave the button dead.
 */

import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { useStartNewFlow } from "../use-start-new-flow";

const addFlow = jest.fn();
const navigate = jest.fn();
const openWelcome = jest.fn();

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => addFlow,
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => navigate,
}));

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useParams: () => ({ folderId: "project-1" }),
}));

jest.mock("@/stores/flowBuilderWelcomeStore", () => ({
  __esModule: true,
  default: (selector: (state: { open: jest.Mock }) => unknown) =>
    selector({ open: openWelcome }),
}));

describe("useStartNewFlow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    addFlow.mockReset();
  });

  it("creates one flow and opens it when clicked again while creating", async () => {
    let finishCreate: (id: string) => void = () => {};
    addFlow.mockReturnValue(
      new Promise<string>((resolve) => {
        finishCreate = resolve;
      }),
    );
    const { result } = renderHook(() => useStartNewFlow());

    let firstClick: Promise<void> = Promise.resolve();
    await act(async () => {
      firstClick = result.current();
      void result.current();
    });
    expect(addFlow).toHaveBeenCalledTimes(1);

    await act(async () => {
      finishCreate("flow-1");
      await firstClick;
    });
    expect(openWelcome).toHaveBeenCalledWith("flow-1");
    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith("/flow/flow-1/folder/project-1");
  });

  it("allows another try after a failed create", async () => {
    addFlow.mockRejectedValueOnce(new Error("create failed"));
    addFlow.mockResolvedValueOnce("flow-2");
    const { result } = renderHook(() => useStartNewFlow());

    await act(async () => {
      await expect(result.current()).rejects.toThrow("create failed");
    });
    expect(navigate).not.toHaveBeenCalled();

    await act(async () => {
      await result.current();
    });
    expect(addFlow).toHaveBeenCalledTimes(2);
    expect(navigate).toHaveBeenCalledWith("/flow/flow-2/folder/project-1");
  });
});

// The two pages as the app's routes have them: changing project keeps the same
// list page mounted, opening a flow replaces it.
function ListPage() {
  const startNewFlow = useStartNewFlow();
  return <button onClick={() => void startNewFlow()}>New Flow</button>;
}

describe("useStartNewFlow with the real router", () => {
  const LIST_URL = "/all/folder/project-1";
  const CANVAS_URL = "/flow/flow-1/folder/project-1";
  let router: ReturnType<typeof createBrowserRouter>;

  const newFlowButton = () => screen.getByRole("button", { name: "New Flow" });
  const nextTask = () => new Promise((resolve) => setTimeout(resolve));

  // jsdom has no Request, and the router builds one even with no loaders to run.
  const jsdomRequest = globalThis.Request;
  beforeAll(() => {
    globalThis.Request = class {
      method = "GET";
      signal?: AbortSignal;
      constructor(
        public url: string,
        init?: RequestInit,
      ) {
        this.signal = init?.signal ?? undefined;
      }
    } as unknown as typeof Request;
  });
  afterAll(() => {
    globalThis.Request = jsdomRequest;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    addFlow.mockReset();
    addFlow.mockResolvedValueOnce("flow-1").mockResolvedValueOnce("flow-2");
    window.history.pushState(null, "", LIST_URL);
    router = createBrowserRouter([
      {
        path: "/all",
        element: <ListPage />,
        children: [{ path: "folder/:folderId", element: <div /> }],
      },
      { path: "/flow/:id/folder/:folderId", element: <div>Canvas</div> },
    ]);
    navigate.mockImplementation((to: string) => router.navigate(to));
    render(<RouterProvider router={router} />);
  });

  afterEach(() => {
    router.dispose();
    navigate.mockReset();
  });

  // RouterProvider commits a route change in a transition, and act() holds that
  // work until its callback ends: inside it, navigate() has returned and the URL
  // has moved while the list page is still on screen.
  it("ignores a click that arrives before the new route commits", async () => {
    const button = newFlowButton();

    await act(async () => {
      fireEvent.click(button);
      await nextTask();
      expect(window.location.pathname).toBe(CANVAS_URL);
      expect(button).toBeInTheDocument();

      fireEvent.click(button);
      await nextTask();
    });

    expect(addFlow).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Canvas")).toBeInTheDocument();
  });

  it("creates again after coming back from the canvas", async () => {
    fireEvent.click(newFlowButton());
    await screen.findByText("Canvas");

    await act(async () => {
      await router.navigate(-1);
    });
    fireEvent.click(await screen.findByRole("button", { name: "New Flow" }));

    await screen.findByText("Canvas");
    expect(addFlow).toHaveBeenCalledTimes(2);
    expect(window.location.pathname).toBe("/flow/flow-2/folder/project-1");
  });

  it.each<[string, () => Promise<void>, string]>([
    [
      "another navigation",
      () => router.navigate("/all/folder/other"),
      "/all/folder/other",
    ],
    ["the back button", () => router.navigate(-1), LIST_URL],
  ])(
    "creates again when %s overtakes the route change",
    async (_, overtake, url) => {
      const button = newFlowButton();

      await act(async () => {
        fireEvent.click(button);
        await nextTask();
        await overtake();
      });
      expect(window.location.pathname).toBe(url);
      expect(button).toBeInTheDocument();

      fireEvent.click(button);
      await screen.findByText("Canvas");
      expect(addFlow).toHaveBeenCalledTimes(2);
    },
  );

  it("creates again when the navigation is blocked", async () => {
    router.getBlocker("test", () => true);
    const button = newFlowButton();

    fireEvent.click(button);
    await waitFor(() => expect(navigate).toHaveBeenCalledTimes(1));
    await act(nextTask);
    expect(window.location.pathname).toBe(LIST_URL);

    fireEvent.click(button);
    await waitFor(() => expect(addFlow).toHaveBeenCalledTimes(2));
  });
});
