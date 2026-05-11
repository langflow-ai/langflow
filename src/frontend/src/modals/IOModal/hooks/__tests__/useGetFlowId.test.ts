import { v5 as uuidv5 } from "uuid";

// Mock the stores before importing the hook
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

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: jest.fn(),
}));

import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useGetFlowId } from "../useGetFlowId";

const mockFlowStore = useFlowStore as unknown as jest.Mock;
const mockFlowsManagerStore = useFlowsManagerStore as unknown as jest.Mock;
const mockUtilityStore = useUtilityStore as unknown as jest.Mock;
const mockAuthStore = useAuthStore as unknown as jest.Mock;

const REAL_FLOW_ID = "real-flow-id-123";
const CLIENT_ID = "client-id-456";
const USER_ID = "user-id-789";

describe("useGetFlowId", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_return_real_flow_id_when_not_playground", () => {
    mockFlowStore.mockReturnValue(false); // playgroundPage
    mockFlowsManagerStore.mockReturnValue(REAL_FLOW_ID); // currentFlowId
    mockUtilityStore.mockReturnValue(CLIENT_ID); // clientId
    mockAuthStore.mockReturnValue(false); // isAuthenticated (first call)

    // Re-mock to handle multiple selector calls
    let authCallCount = 0;
    mockAuthStore.mockImplementation((selector: any) => {
      const state = {
        isAuthenticated: false,
        autoLogin: false,
        userData: null,
      };
      return selector(state);
    });

    mockFlowStore.mockImplementation((selector: any) => {
      return selector({ playgroundPage: false });
    });

    mockFlowsManagerStore.mockImplementation((selector: any) => {
      return selector({ currentFlowId: REAL_FLOW_ID });
    });

    mockUtilityStore.mockImplementation((selector: any) => {
      return selector({ clientId: CLIENT_ID });
    });

    const result = useGetFlowId();
    expect(result).toBe(REAL_FLOW_ID);
  });

  it("should_use_client_id_for_uuid_when_anonymous_on_playground", () => {
    mockFlowStore.mockImplementation((selector: any) =>
      selector({ playgroundPage: true }),
    );
    mockFlowsManagerStore.mockImplementation((selector: any) =>
      selector({ currentFlowId: REAL_FLOW_ID }),
    );
    mockUtilityStore.mockImplementation((selector: any) =>
      selector({ clientId: CLIENT_ID }),
    );
    mockAuthStore.mockImplementation((selector: any) =>
      selector({
        isAuthenticated: false,
        autoLogin: true,
        userData: null,
      }),
    );

    const result = useGetFlowId();
    const expected = uuidv5(`${CLIENT_ID}_${REAL_FLOW_ID}`, uuidv5.DNS);
    expect(result).toBe(expected);
  });

  it("should_use_user_id_for_uuid_when_authenticated_on_playground", () => {
    mockFlowStore.mockImplementation((selector: any) =>
      selector({ playgroundPage: true }),
    );
    mockFlowsManagerStore.mockImplementation((selector: any) =>
      selector({ currentFlowId: REAL_FLOW_ID }),
    );
    mockUtilityStore.mockImplementation((selector: any) =>
      selector({ clientId: CLIENT_ID }),
    );
    mockAuthStore.mockImplementation((selector: any) =>
      selector({
        isAuthenticated: true,
        autoLogin: false,
        userData: { id: USER_ID },
      }),
    );

    const result = useGetFlowId();
    const expected = uuidv5(`${USER_ID}_${REAL_FLOW_ID}`, uuidv5.DNS);
    expect(result).toBe(expected);
  });

  it("should_use_client_id_when_autologin_even_if_authenticated", () => {
    mockFlowStore.mockImplementation((selector: any) =>
      selector({ playgroundPage: true }),
    );
    mockFlowsManagerStore.mockImplementation((selector: any) =>
      selector({ currentFlowId: REAL_FLOW_ID }),
    );
    mockUtilityStore.mockImplementation((selector: any) =>
      selector({ clientId: CLIENT_ID }),
    );
    mockAuthStore.mockImplementation((selector: any) =>
      selector({
        isAuthenticated: true,
        autoLogin: true,
        userData: { id: USER_ID },
      }),
    );

    const result = useGetFlowId();
    const expected = uuidv5(`${CLIENT_ID}_${REAL_FLOW_ID}`, uuidv5.DNS);
    expect(result).toBe(expected);
  });

  it("should_use_client_id_when_user_data_has_no_id", () => {
    mockFlowStore.mockImplementation((selector: any) =>
      selector({ playgroundPage: true }),
    );
    mockFlowsManagerStore.mockImplementation((selector: any) =>
      selector({ currentFlowId: REAL_FLOW_ID }),
    );
    mockUtilityStore.mockImplementation((selector: any) =>
      selector({ clientId: CLIENT_ID }),
    );
    mockAuthStore.mockImplementation((selector: any) =>
      selector({
        isAuthenticated: true,
        autoLogin: false,
        userData: null,
      }),
    );

    const result = useGetFlowId();
    const expected = uuidv5(`${CLIENT_ID}_${REAL_FLOW_ID}`, uuidv5.DNS);
    expect(result).toBe(expected);
  });
});
