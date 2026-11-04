import { act, renderHook, waitFor } from "@testing-library/react";
import useFileDrop from "../use-on-file-drop";

const mockUploadFlow = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();

jest.mock("@/hooks/flows/use-upload-flow", () => ({
  __esModule: true,
  default: () => mockUploadFlow,
}));

jest.mock("../../../../stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
    }),
}));

describe("dashboard flow upload errors", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows the validation detail instead of the generic Axios message", async () => {
    const message =
      "A flow can have only one trigger. Remove the extra triggers and try again.";
    mockUploadFlow.mockRejectedValue({
      message: "Request failed with status code 422",
      response: { status: 422, data: { detail: [{ msg: message }] } },
    });
    const { result } = renderHook(() => useFileDrop("flows"));
    const event = {
      preventDefault: jest.fn(),
      dataTransfer: {
        types: ["Files"],
        files: [new File(["{}"], "flow.json", { type: "application/json" })],
      },
    };

    act(() => result.current(event));

    await waitFor(() =>
      expect(mockSetErrorData).toHaveBeenLastCalledWith({
        title: "Error occurred while uploading file",
        list: [message],
      }),
    );
    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });
});
