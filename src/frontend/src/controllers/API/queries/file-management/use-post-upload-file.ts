import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { FileType } from "@/types/file_management";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { getUniqueFilename } from "./upload-name-utils";

interface IPostUploadFile {
  file: File;
}

export const usePostUploadFileV2: useMutationFunctionType<
  undefined,
  IPostUploadFile
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postUploadFileFn = async (payload: IPostUploadFile): Promise<any> => {
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

    const newFile = {
      id: "temp",
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
      return [...old.filter((file) => file.id !== "temp"), newFile];
    });

    try {
      const response = await api.post<any>(
        `${getURL("FILE_MANAGEMENT", {}, true)}`,
        formData,
        {
          onUploadProgress: (progressEvent) => {
            if (progressEvent.progress) {
              queryClient.setQueryData(["useGetFilesV2"], (old: any) => {
                if (!Array.isArray(old)) return [];
                return old.map((file: any) => {
                  if (file?.id === "temp") {
                    return { ...file, progress: progressEvent.progress };
                  }
                  return file;
                });
              });
            }
          },
        },
      );
      return response.data;
    } catch (e) {
      queryClient.setQueryData(["useGetFilesV2"], (old: FileType[]) => {
        if (!Array.isArray(old)) return [];
        return old.map((file: any) => {
          if (file?.id === "temp") {
            return { ...file, progress: -1 };
          }
          return file;
        });
      });
      throw e;
    }
  };

  const mutation: UseMutationResult<IPostUploadFile, any, IPostUploadFile> =
    mutate(
      ["usePostUploadFileV2"],
      async (payload: IPostUploadFile) => {
        const res = await postUploadFileFn(payload);
        return res;
      },
      {
        onSettled: (data, error, variables, context) => {
          if (!error) {
            queryClient.invalidateQueries({
              queryKey: ["useGetFilesV2"],
            });
          }
          options?.onSettled?.(data, error, variables, context);
        },
        retry: 0,
        ...options,
      },
    );

  return mutation;
};
