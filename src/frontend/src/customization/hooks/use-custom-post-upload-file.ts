import { usePostUploadFileV2 } from "@/controllers/API/queries/file-management";
import type { useMutationFunctionType } from "@/types/api";

interface IPostUploadFile {
  file: File;
}

export const customPostUploadFileV2: useMutationFunctionType<
  undefined,
  IPostUploadFile
> = (options?) => {
  return usePostUploadFileV2(options);
};
