import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import type { useMutationFunctionType } from "@/types/api";

interface IPostUploadFile {
  file: File;
  id: string;
}

export const customUsePostUploadFile: useMutationFunctionType<
  undefined,
  IPostUploadFile
> = (options?) => {
  return usePostUploadFile(options);
};
