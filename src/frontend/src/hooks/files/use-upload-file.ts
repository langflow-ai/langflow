import { customPostUploadFileV2 } from "@/customization/hooks/use-custom-post-upload-file";
import { createFileUpload } from "@/helpers/create-file-upload";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";

const useUploadFile = ({
  types,
  multiple,
}: {
  types?: string[];
  multiple?: boolean;
}) => {
  const { mutateAsync: uploadFileMutation } = customPostUploadFileV2();
  const { validateFileSize } = useFileSizeValidator();

  const getFilesToUpload = async ({
    files,
  }: {
    files?: File[];
  }): Promise<File[]> => {
    if (!files) {
      files = await createFileUpload({
        accept: types?.map((type) => `.${type}`).join(",") ?? "",
        multiple: multiple ?? false,
      });
    }
    return files;
  };

  const uploadFile = async ({
    files,
  }: {
    files?: File[];
  }): Promise<string[]> => {
    try {
      const filesToUpload = await getFilesToUpload({ files });
      const filesIds: string[] = [];

      for (const file of filesToUpload) {
        validateFileSize(file);
        // Check if file extension is allowed
        const fileExtension = file.name.split(".").pop()?.toLowerCase();
        if (!fileExtension || (types && !types.includes(fileExtension))) {
          throw new Error(
            `File type ${fileExtension} not allowed. Allowed types: ${types?.join(", ")}`,
          );
        }
        if (!fileExtension) {
          throw new Error("File type not allowed");
        }
        if (!multiple && filesToUpload.length !== 1) {
          throw new Error("Multiple files are not allowed");
        }

        const res = await uploadFileMutation({
          file,
        });
        filesIds.push(res.path);
      }
      return filesIds;
    } catch (e) {
      throw e;
    }
  };

  return uploadFile;
};

export default useUploadFile;
