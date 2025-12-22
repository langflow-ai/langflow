import { render, screen, waitFor } from "@testing-library/react";
import AuthenticatedImage from "../authenticated-image";
import { api } from "@/controllers/API/api";

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: jest.fn(),
  },
}));

const mockCreateObjectURL = jest.fn();
const mockRevokeObjectURL = jest.fn();

describe("AuthenticatedImage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;
    mockCreateObjectURL.mockReturnValue("blob:mock-url");
  });

  it("should_render_loading_state_when_fetching_image", () => {
    (api.get as jest.Mock).mockImplementation(
      () => new Promise(() => {}), // Never resolves to keep loading state
    );

    render(
      <AuthenticatedImage
        src="/api/v1/files/images/test"
        alt="test image"
        className="test-class"
      />,
    );

    expect(screen.getByTestId("authenticated-image-loading")).toBeInTheDocument();
  });

  it("should_render_image_when_fetch_succeeds", async () => {
    const mockBlob = new Blob(["test"], { type: "image/png" });
    (api.get as jest.Mock).mockResolvedValue({ data: mockBlob });

    render(
      <AuthenticatedImage
        src="/api/v1/files/images/test"
        alt="test image"
        className="test-class"
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("authenticated-image")).toBeInTheDocument();
    });

    const img = screen.getByTestId("authenticated-image");
    expect(img).toHaveAttribute("src", "blob:mock-url");
    expect(img).toHaveAttribute("alt", "test image");
    expect(img).toHaveClass("test-class");
  });

  it("should_render_error_state_when_fetch_fails", async () => {
    const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation();
    (api.get as jest.Mock).mockRejectedValue(new Error("Network error"));

    render(
      <AuthenticatedImage
        src="/api/v1/files/images/test"
        alt="test image"
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("authenticated-image-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Failed to load image")).toBeInTheDocument();
    consoleErrorSpy.mockRestore();
  });

  it("should_call_api_with_correct_params", async () => {
    const mockBlob = new Blob(["test"], { type: "image/png" });
    (api.get as jest.Mock).mockResolvedValue({ data: mockBlob });

    render(
      <AuthenticatedImage
        src="/api/v1/files/images/flow-id/image.png"
        alt="test"
      />,
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/v1/files/images/flow-id/image.png", {
        responseType: "blob",
      });
    });
  });

  it("should_create_object_url_from_blob_response", async () => {
    const mockBlob = new Blob(["test"], { type: "image/png" });
    (api.get as jest.Mock).mockResolvedValue({ data: mockBlob });

    render(<AuthenticatedImage src="/api/v1/files/images/test" alt="test" />);

    await waitFor(() => {
      expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
    });
  });

  it("should_revoke_object_url_on_unmount", async () => {
    const mockBlob = new Blob(["test"], { type: "image/png" });
    (api.get as jest.Mock).mockResolvedValue({ data: mockBlob });

    const { unmount } = render(
      <AuthenticatedImage src="/api/v1/files/images/test" alt="test" />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("authenticated-image")).toBeInTheDocument();
    });

    unmount();

    expect(mockRevokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  it("should_apply_className_to_loading_state", () => {
    (api.get as jest.Mock).mockImplementation(() => new Promise(() => {}));

    render(
      <AuthenticatedImage
        src="/api/v1/files/images/test"
        alt="test"
        className="custom-class"
      />,
    );

    const loadingDiv = screen.getByTestId("authenticated-image-loading");
    expect(loadingDiv).toHaveClass("custom-class");
  });

  it("should_apply_className_to_error_state", async () => {
    jest.spyOn(console, "error").mockImplementation();
    (api.get as jest.Mock).mockRejectedValue(new Error("Error"));

    render(
      <AuthenticatedImage
        src="/api/v1/files/images/test"
        alt="test"
        className="custom-class"
      />,
    );

    await waitFor(() => {
      const errorDiv = screen.getByTestId("authenticated-image-error");
      expect(errorDiv).toHaveClass("custom-class");
    });
  });
});
