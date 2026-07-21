/**
 * Tests for the annotation API hooks.
 *
 * Verifies URL routing and request payloads for the
 * /api/v1/annotation-projects endpoints.
 */

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApiPatch = jest.fn();
const mockApiPut = jest.fn();
const mockApiDelete = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
    post: (...args: unknown[]) => mockApiPost(...args),
    patch: (...args: unknown[]) => mockApiPatch(...args),
    put: (...args: unknown[]) => mockApiPut(...args),
    delete: (...args: unknown[]) => mockApiDelete(...args),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `api/v1/${key.toLowerCase()}`,
}));

const mockRefetchQueries = jest.fn();
const mockSetQueryData = jest.fn();
const mockRemoveQueries = jest.fn();

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: jest.fn((_key: unknown, fn: () => Promise<unknown>) => {
      void fn();
      return { data: null, isFetched: false, refetch: jest.fn() };
    }),
    mutate: jest.fn(
      (
        _key: unknown,
        fn: (variables: unknown) => Promise<unknown>,
        options?: { onSuccess?: (...args: unknown[]) => void },
      ) => ({
        mutate: async (variables: unknown) => {
          const data = await fn(variables);
          options?.onSuccess?.(data, variables, undefined, undefined);
          return data;
        },
      }),
    ),
    queryClient: {
      refetchQueries: (...args: unknown[]) => mockRefetchQueries(...args),
      setQueryData: (...args: unknown[]) => mockSetQueryData(...args),
      removeQueries: (...args: unknown[]) => mockRemoveQueries(...args),
    },
  })),
}));

import {
  useDeleteAnnotationImage,
  useGetAnnotationProjects,
  usePostAnnotationImages,
  usePostAnnotationProject,
  usePutImageAnnotations,
} from "..";

const PROJECT_ID = "project-1";
const IMAGE_ID = "image-1";

describe("annotation API hooks", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiGet.mockResolvedValue({ data: [] });
    mockApiPost.mockResolvedValue({ data: {} });
    mockApiPatch.mockResolvedValue({ data: {} });
    mockApiPut.mockResolvedValue({ data: {} });
    mockApiDelete.mockResolvedValue({ data: {} });
  });

  it("useGetAnnotationProjects fetches the projects list endpoint", async () => {
    useGetAnnotationProjects({});
    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(mockApiGet).toHaveBeenCalledWith("api/v1/annotation_projects/");
  });

  it("usePostAnnotationProject posts the create payload and refetches the list", async () => {
    const payload = {
      name: "Cats",
      description: "demo",
      labels: [{ value: "cat", background: "#FFA39E" }],
    };
    mockApiPost.mockResolvedValue({ data: { id: PROJECT_ID, ...payload } });

    const { mutate } = usePostAnnotationProject();
    await mutate(payload);

    expect(mockApiPost).toHaveBeenCalledWith(
      "api/v1/annotation_projects/",
      payload,
    );
    expect(mockRefetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetAnnotationProjects"],
    });
  });

  it("usePostAnnotationImages uploads multipart form data to the nested endpoint", async () => {
    const file = new File(["fake-png"], "cat.png", { type: "image/png" });
    mockApiPost.mockResolvedValue({ data: [{ id: IMAGE_ID }] });

    const { mutate } = usePostAnnotationImages();
    await mutate({ projectId: PROJECT_ID, files: [file] });

    const [url, body] = mockApiPost.mock.calls[0] as [string, FormData];
    expect(url).toBe(`api/v1/annotation_projects/${PROJECT_ID}/images`);
    expect(body).toBeInstanceOf(FormData);
    expect(body.getAll("files")).toHaveLength(1);
  });

  it("usePutImageAnnotations sends the LS-compatible result to the annotations endpoint", async () => {
    const result = [
      {
        id: "region-1",
        type: "rectanglelabels",
        from_name: "label",
        to_name: "image",
        origin: "manual",
        original_width: 800,
        original_height: 600,
        value: {
          x: 10,
          y: 20,
          width: 30,
          height: 40,
          rotation: 0,
          rectanglelabels: ["cat"],
        },
      },
    ];
    mockApiPut.mockResolvedValue({ data: { result, updated_at: "now" } });

    const { mutate } = usePutImageAnnotations();
    await mutate({
      projectId: PROJECT_ID,
      imageId: IMAGE_ID,
      result,
      lead_time: 1.5,
    });

    expect(mockApiPut).toHaveBeenCalledWith(
      `api/v1/annotation_projects/${PROJECT_ID}/images/${IMAGE_ID}/annotations`,
      { result, lead_time: 1.5 },
    );
    expect(mockSetQueryData).toHaveBeenCalledWith(
      ["useGetImageAnnotations", IMAGE_ID],
      { result, updated_at: "now" },
    );
  });

  it("useDeleteAnnotationImage deletes the nested image and cleans up caches", async () => {
    const { mutate } = useDeleteAnnotationImage();
    await mutate({ projectId: PROJECT_ID, imageId: IMAGE_ID });

    expect(mockApiDelete).toHaveBeenCalledWith(
      `api/v1/annotation_projects/${PROJECT_ID}/images/${IMAGE_ID}`,
    );
    expect(mockRemoveQueries).toHaveBeenCalledWith({
      queryKey: ["useGetAnnotationImageUrl", IMAGE_ID],
    });
    expect(mockRemoveQueries).toHaveBeenCalledWith({
      queryKey: ["useGetImageAnnotations", IMAGE_ID],
    });
  });
});
