/**
 * Tests for the text-annotation API hooks.
 *
 * Verifies URL routing and request payloads for the
 * /api/v1/text-annotation-projects endpoints.
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
  useDeleteTextAnnotationProject,
  useDeleteTextAnnotationTask,
  useGetTextAnnotationProject,
  useGetTextAnnotationProjects,
  usePostTextAnnotationImportCsv,
  usePostTextAnnotationImportDatabase,
  usePostTextAnnotationProject,
  usePostTextAnnotationTasks,
  usePreviewTextAnnotationDatabaseImport,
  usePutTextTaskAnnotations,
} from "..";

const PROJECT_ID = "project-1";
const TASK_ID = "task-1";

describe("text-annotation API hooks", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiGet.mockResolvedValue({ data: [] });
    mockApiPost.mockResolvedValue({ data: {} });
    mockApiPatch.mockResolvedValue({ data: {} });
    mockApiPut.mockResolvedValue({ data: {} });
    mockApiDelete.mockResolvedValue({ data: {} });
  });

  it("useGetTextAnnotationProjects fetches the projects list endpoint", async () => {
    useGetTextAnnotationProjects({});
    await Promise.resolve();
    expect(mockApiGet).toHaveBeenCalledWith("api/v1/text_annotation_projects/");
  });

  it("useGetTextAnnotationProject fetches the project detail endpoint", async () => {
    useGetTextAnnotationProject({ projectId: PROJECT_ID });
    await Promise.resolve();
    expect(mockApiGet).toHaveBeenCalledWith(
      `api/v1/text_annotation_projects/${PROJECT_ID}`,
    );
  });

  it("usePostTextAnnotationProject posts the create payload", async () => {
    const payload = {
      name: "NER",
      task_type: "ner" as const,
      entity_labels: [{ value: "person" }],
      category_labels: [],
    };
    const { mutate } = usePostTextAnnotationProject({});
    await mutate(payload);
    expect(mockApiPost).toHaveBeenCalledWith(
      "api/v1/text_annotation_projects/",
      payload,
    );
    expect(mockRefetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetTextAnnotationProjects"],
    });
  });

  it("usePostTextAnnotationTasks posts texts to the tasks endpoint", async () => {
    const { mutate } = usePostTextAnnotationTasks({});
    await mutate({
      projectId: PROJECT_ID,
      tasks: [{ text: "hello" }],
      source: "paste",
    });
    expect(mockApiPost).toHaveBeenCalledWith(
      `api/v1/text_annotation_projects/${PROJECT_ID}/tasks`,
      { tasks: [{ text: "hello" }], source: "paste" },
    );
  });

  it("useDeleteTextAnnotationTask deletes the task endpoint", async () => {
    const { mutate } = useDeleteTextAnnotationTask({});
    await mutate({ projectId: PROJECT_ID, taskId: TASK_ID });
    expect(mockApiDelete).toHaveBeenCalledWith(
      `api/v1/text_annotation_projects/${PROJECT_ID}/tasks/${TASK_ID}`,
    );
  });

  it("usePutTextTaskAnnotations puts the LS-style result", async () => {
    const result = [
      {
        id: "s1",
        type: "labels",
        from_name: "label",
        to_name: "text",
        origin: "manual",
        value: { start: 0, end: 2, text: "张三", labels: ["person"] },
      },
    ];
    const { mutate } = usePutTextTaskAnnotations({});
    await mutate({ projectId: PROJECT_ID, taskId: TASK_ID, result });
    expect(mockApiPut).toHaveBeenCalledWith(
      `api/v1/text_annotation_projects/${PROJECT_ID}/tasks/${TASK_ID}/annotations`,
      { result },
    );
  });

  it("usePostTextAnnotationImportCsv posts multipart form data", async () => {
    const file = new File(["text\nhello"], "data.csv", { type: "text/csv" });
    const { mutate } = usePostTextAnnotationImportCsv({});
    await mutate({ projectId: PROJECT_ID, file, hasHeader: true });
    const [url, formData] = mockApiPost.mock.calls[0];
    expect(url).toBe(
      `api/v1/text_annotation_projects/${PROJECT_ID}/import/csv`,
    );
    expect(formData).toBeInstanceOf(FormData);
    expect((formData.get("file") as File).name).toBe("data.csv");
    expect(formData.get("has_header")).toBe("true");
  });

  it("usePreviewTextAnnotationDatabaseImport posts to the preview endpoint", async () => {
    const { mutate } = usePreviewTextAnnotationDatabaseImport({});
    await mutate({
      projectId: PROJECT_ID,
      connection_uri: "sqlite:///x.db",
      table_name: "docs",
      sample_size: 5,
    });
    expect(mockApiPost).toHaveBeenCalledWith(
      `api/v1/text_annotation_projects/${PROJECT_ID}/import/database/preview`,
      { connection_uri: "sqlite:///x.db", table_name: "docs", sample_size: 5 },
    );
  });

  it("usePostTextAnnotationImportDatabase posts the import config", async () => {
    const { mutate } = usePostTextAnnotationImportDatabase({});
    await mutate({
      projectId: PROJECT_ID,
      connection_uri: "sqlite:///x.db",
      table_name: "docs",
      text_column: "content",
      limit: 100,
    });
    expect(mockApiPost).toHaveBeenCalledWith(
      `api/v1/text_annotation_projects/${PROJECT_ID}/import/database`,
      {
        connection_uri: "sqlite:///x.db",
        table_name: "docs",
        text_column: "content",
        limit: 100,
      },
    );
  });

  it("useDeleteTextAnnotationProject deletes the project endpoint", async () => {
    const { mutate } = useDeleteTextAnnotationProject({});
    await mutate({ projectId: PROJECT_ID });
    expect(mockApiDelete).toHaveBeenCalledWith(
      `api/v1/text_annotation_projects/${PROJECT_ID}`,
    );
  });
});
