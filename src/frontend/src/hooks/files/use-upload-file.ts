import { customPostUploadFileV2 } from "@/customization/hooks/use-custom-post-upload-file";
import { createFileUpload } from "@/helpers/create-file-upload";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";

const useUploadFile = ({
  types,
  multiple,
  webkitdirectory,
}: {
  types?: string[];
  multiple?: boolean;
  webkitdirectory?: boolean;
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
        webkitdirectory: webkitdirectory ?? false,
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

      // Filter files by supported types when using folder selection
      let validFiles = filesToUpload;
      if (webkitdirectory && types) {
        validFiles = filesToUpload.filter((file) => {
          const fileExtension = file.name.split(".").pop()?.toLowerCase();
          return fileExtension && types.includes(fileExtension);
        });

        if (validFiles.length === 0) {
          throw new Error(
            `No supported files found in folder. Allowed types: ${types?.join(", ")}`,
          );
        }
      }

      for (const file of validFiles) {
        validateFileSize(file);
        // Check if file extension is allowed (for non-folder selection)
        if (!webkitdirectory) {
          const fileExtension = file.name.split(".").pop()?.toLowerCase();
          if (!fileExtension || (types && !types.includes(fileExtension))) {
            throw new Error(
              `File type ${fileExtension} not allowed. Allowed types: ${types?.join(", ")}`,
            );
          }
          if (!multiple && filesToUpload.length !== 1) {
            throw new Error("Multiple files are not allowed");
          }
        }

        const res = await uploadFileMutation({
          file,
        });
        filesIds.push(res.path);
      }
      return filesIds;
    } catch (e: any) {
      const errorMessage =
        e?.response?.data?.detail ||
        e?.message ||
        "An error occurred while uploading the file";
      throw new Error(errorMessage);
    }
  };

  return uploadFile;
};

export default useUploadFile;
