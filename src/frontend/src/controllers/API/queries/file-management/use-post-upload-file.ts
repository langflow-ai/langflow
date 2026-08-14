import type { QueryClient, UseMutationResult } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import type { useMutationFunctionType } from "@/types/api";
import type { FileType } from "@/types/file_management";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { getUniqueFilename } from "./upload-name-utils";

interface IPostUploadFile {
  file: File;
}

let optimisticUploadSequence = 0;

interface OptimisticUploadState {
  inFlightIds: Set<string>;
  invalidationPending: boolean;
}

const optimisticUploadStates = new WeakMap<
  QueryClient,
  OptimisticUploadState
>();

const getOptimisticUploadState = (
  queryClient: QueryClient,
): OptimisticUploadState => {
  const existingState = optimisticUploadStates.get(queryClient);
  if (existingState) return existingState;

  const state = {
    inFlightIds: new Set<string>(),
    invalidationPending: false,
  };
  optimisticUploadStates.set(queryClient, state);
  return state;
};

export const createOptimisticUploadId = (): string =>
  `temp-${Date.now()}-${optimisticUploadSequence++}`;

export const usePostUploadFileV2: useMutationFunctionType<
  undefined,
  IPostUploadFile,
  FileType,
  AxiosError<{ detail?: string }>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const optimisticUploadState = getOptimisticUploadState(queryClient);

  const postUploadFileFn = async (
    payload: IPostUploadFile,
  ): Promise<FileType> => {
    const formData = new FormData();

    // Build set of existing paths (server-side path is typically full filename)
    // Use the existing queryClient from the hook; do not call hooks here.
    const existingFiles: FileType[] =
      (queryClient.getQueryData(["useGetFilesV2"]) as FileType[]) ?? [];
    const existingNames = new Set<string>(
      Array.isArray(existingFiles) ? existingFiles.map((f) => f.path) : [],
    );

    // For files from folder selection, create a new File object with just the filename
    // to avoid including the folder path in the upload, and ensure unique naming.
    // Keep a UI-friendly File with webkitRelativePath (updated leaf name) for hierarchy rendering.
    let fileToUpload = payload.file;
    const targetName = getUniqueFilename(payload.file.name, existingNames);

    if (payload.file.webkitRelativePath || targetName !== payload.file.name) {
      fileToUpload = new File([payload.file], targetName, {
        type: payload.file.type,
        lastModified: payload.file.lastModified,
      });
    }

    let fileForUi: File = fileToUpload;
    if (payload.file.webkitRelativePath) {
      const parts = payload.file.webkitRelativePath.split("/").filter(Boolean);
      if (parts.length > 0) {
        parts[parts.length - 1] = targetName;
        try {
          Object.defineProperty(fileForUi, "webkitRelativePath", {
            value: parts.join("/"),
            enumerable: true,
          });
        } catch {}
      }
    }

    formData.append("file", fileToUpload);
    const data = new Date().toISOString().split("Z")[0];
    const optimisticUploadId = createOptimisticUploadId();
    optimisticUploadState.inFlightIds.add(optimisticUploadId);

    const newFile = {
      id: optimisticUploadId,
      name: fileToUpload.name.split(".").slice(0, -1).join("."),
      path: fileToUpload.name,
      size: fileToUpload.size,
      file: fileForUi,
      updated_at: data,
      created_at: data,
      progress: 0,
    };
    queryClient.setQueryData(["useGetFilesV2"], (old: FileType[]) => {
      if (!Array.isArray(old)) return [newFile];
      return [...old, newFile];
    });

    try {
      const response = await api.post<FileType>(
        `${getURL("FILE_MANAGEMENT", {}, true)}`,
        formData,
        {
          onUploadProgress: (progressEvent) => {
            if (progressEvent.progress) {
              queryClient.setQueryData<FileType[]>(["useGetFilesV2"], (old) => {
                if (!Array.isArray(old)) return [];
                return old.map((file) => {
                  if (file?.id === optimisticUploadId) {
                    return { ...file, progress: progressEvent.progress };
                  }
                  return file;
                });
              });
            }
          },
        },
      );

      // Replace the optimistic "temp" entry with the actual server data so
      // that file.path in the cache matches the path returned to callers
      // (via handleUpload → internalSelectedFiles). Without this, there is
      // a race window where the optimistic path (just the filename) differs
      // from the server path (user_id/filename), causing checkboxes to
      // appear unchecked until the background refetch completes.
      queryClient.setQueryData<FileType[]>(["useGetFilesV2"], (old) => {
        if (!Array.isArray(old)) return [response.data];
        return old.map((file) =>
          file?.id === optimisticUploadId ? { ...response.data } : file,
        );
      });

      return response.data;
    } catch (e) {
      queryClient.setQueryData(["useGetFilesV2"], (old: FileType[]) => {
        if (!Array.isArray(old)) return [];
        return old.map((file) => {
          if (file?.id === optimisticUploadId) {
            return { ...file, progress: -1 };
          }
          return file;
        });
      });
      throw e;
    } finally {
      optimisticUploadState.inFlightIds.delete(optimisticUploadId);
    }
  };

  const mutation: UseMutationResult<
    FileType,
    AxiosError<{ detail?: string }>,
    IPostUploadFile
  > = mutate(
    ["usePostUploadFileV2"],
    async (payload: IPostUploadFile) => {
      const res = await postUploadFileFn(payload);
      return res;
    },
    {
      retry: 0,
      ...options,
      onSettled: async (data, error, variables, onMutateResult, context) => {
        if (!error) {
          optimisticUploadState.invalidationPending = true;
        }

        if (
          optimisticUploadState.inFlightIds.size === 0 &&
          optimisticUploadState.invalidationPending
        ) {
          optimisticUploadState.invalidationPending = false;
          await queryClient.invalidateQueries({
            queryKey: ["useGetFilesV2"],
          });
        }

        await options?.onSettled?.(
          data,
          error,
          variables,
          onMutateResult,
          context,
        );
      },
    },
  );

  return mutation;
};
