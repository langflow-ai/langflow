import type { QueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { UseRequestProcessor } from "@/controllers/API/services/request-processor";
import type { FileType } from "@/types/file_management";
import { usePostUploadFileV2 } from "../use-post-upload-file";

jest.mock("@/controllers/API/api", () => ({
  api: { post: jest.fn() },
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(),
}));

const createDeferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const makeServerFile = (id: string, path: string): FileType => ({
  id,
  user_id: "user-1",
  provider: "local",
  name: path.replace(/\.txt$/, ""),
  path: `user-1/${path}`,
  created_at: "2026-08-13T00:00:00",
  updated_at: "2026-08-13T00:00:00",
  size: 1,
});

interface UploadPayload {
  file: File;
}

interface UploadMutationOptions {
  onSettled?: (
    data: FileType | undefined,
    error: unknown | null,
    variables: UploadPayload,
    onMutateResult: unknown,
    context: unknown,
  ) => unknown;
}

describe("usePostUploadFileV2 optimistic cache", () => {
  it("defers invalidation until reverse-order concurrent uploads settle", async () => {
    let cachedFiles: FileType[] = [];
    let serverFiles: FileType[] = [];
    const queryClient = {
      getQueryData: jest.fn(() => cachedFiles),
      setQueryData: jest.fn(
        (
          _key: string[],
          updater: (current: FileType[]) => FileType[] | undefined,
        ) => {
          cachedFiles = updater(cachedFiles) ?? cachedFiles;
        },
      ),
      invalidateQueries: jest.fn(async () => {
        cachedFiles = [...serverFiles];
      }),
    } as unknown as QueryClient;

    (UseRequestProcessor as jest.Mock).mockReturnValue({
      queryClient,
      mutate: (
        _key: string[],
        mutationFn: (payload: UploadPayload) => Promise<FileType>,
        mutationOptions?: UploadMutationOptions,
      ) => ({
        mutateAsync: async (payload: UploadPayload) => {
          try {
            const data = await mutationFn(payload);
            await mutationOptions?.onSettled?.(
              data,
              null,
              payload,
              undefined,
              {},
            );
            return data;
          } catch (error) {
            await mutationOptions?.onSettled?.(
              undefined,
              error,
              payload,
              undefined,
              {},
            );
            throw error;
          }
        },
      }),
    });

    const firstResponse = createDeferred<{ data: FileType }>();
    const secondResponse = createDeferred<{ data: FileType }>();
    (api.post as jest.Mock)
      .mockReturnValueOnce(firstResponse.promise)
      .mockReturnValueOnce(secondResponse.promise);

    const consumerOnSettled = jest.fn();
    const upload = usePostUploadFileV2({
      onSettled: consumerOnSettled,
    }).mutateAsync;
    const firstUpload = upload({ file: new File(["a"], "first.txt") });
    const secondUpload = upload({ file: new File(["b"], "second.txt") });

    expect(cachedFiles).toHaveLength(2);
    expect(new Set(cachedFiles.map(({ id }) => id)).size).toBe(2);
    expect(cachedFiles.map(({ path }) => path)).toEqual([
      "first.txt",
      "second.txt",
    ]);

    const secondFile = makeServerFile("server-2", "second.txt");
    serverFiles = [secondFile];
    secondResponse.resolve({ data: secondFile });
    await expect(secondUpload).resolves.toEqual(secondFile);

    expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
    expect(cachedFiles.map(({ id }) => id)).toEqual([
      expect.stringMatching(/^temp-/),
      "server-2",
    ]);

    const firstFile = makeServerFile("server-1", "first.txt");
    serverFiles = [firstFile, secondFile];
    firstResponse.resolve({ data: firstFile });
    await expect(firstUpload).resolves.toEqual(firstFile);

    expect(queryClient.invalidateQueries).toHaveBeenCalledTimes(1);
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetFilesV2"],
    });
    expect(consumerOnSettled).toHaveBeenCalledTimes(2);
    expect(cachedFiles.map(({ id }) => id)).toEqual(["server-1", "server-2"]);
  });
});
