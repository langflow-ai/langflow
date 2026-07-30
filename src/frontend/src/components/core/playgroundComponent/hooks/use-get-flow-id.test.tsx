import { v5 as uuidv5 } from "uuid";

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: jest.fn(),
}));

import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useGetFlowId } from "./use-get-flow-id";

const mockAuthStore = useAuthStore as unknown as jest.Mock;
const mockFlowStore = useFlowStore as unknown as jest.Mock;
const mockFlowsManagerStore = useFlowsManagerStore as unknown as jest.Mock;
const mockUtilityStore = useUtilityStore as unknown as jest.Mock;

const REAL_FLOW_ID = "real-flow-id";
const CLIENT_ID = "client-id";
const USER_ID = "user-id";

describe("useGetFlowId", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFlowStore.mockImplementation(
      (selector: (state: { playgroundPage: boolean }) => unknown) =>
        selector({ playgroundPage: true }),
    );
    mockFlowsManagerStore.mockImplementation(
      (selector: (state: { currentFlowId: string }) => unknown) =>
        selector({ currentFlowId: REAL_FLOW_ID }),
    );
    mockUtilityStore.mockImplementation(
      (selector: (state: { clientId: string }) => unknown) =>
        selector({ clientId: CLIENT_ID }),
    );
  });

  it("uses the authenticated user id for playground messages", () => {
    mockAuthStore.mockImplementation((selector: (state: object) => unknown) =>
      selector({
        isAuthenticated: true,
        autoLogin: false,
        userData: { id: USER_ID },
      }),
    );

    expect(useGetFlowId()).toBe(
      uuidv5(`${USER_ID}_${REAL_FLOW_ID}`, uuidv5.DNS),
    );
  });

  it("keeps client-scoped ids for anonymous playground messages", () => {
    mockAuthStore.mockImplementation((selector: (state: object) => unknown) =>
      selector({
        isAuthenticated: false,
        autoLogin: true,
        userData: null,
      }),
    );

    expect(useGetFlowId()).toBe(
      uuidv5(`${CLIENT_ID}_${REAL_FLOW_ID}`, uuidv5.DNS),
    );
  });

  it("returns the real flow id outside the playground", () => {
    mockFlowStore.mockImplementation(
      (selector: (state: { playgroundPage: boolean }) => unknown) =>
        selector({ playgroundPage: false }),
    );
    mockAuthStore.mockImplementation((selector: (state: object) => unknown) =>
      selector({
        isAuthenticated: true,
        autoLogin: false,
        userData: { id: USER_ID },
      }),
    );

    expect(useGetFlowId()).toBe(REAL_FLOW_ID);
  });
});
