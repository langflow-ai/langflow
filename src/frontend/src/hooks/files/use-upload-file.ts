import { usePostUploadFileV2 } from "@/controllers/API/queries/file-management/use-post-upload-file";
import { createFileUpload } from "@/helpers/create-file-upload";

const useUploadFile = ({ types }: { types?: string[] }) => {
  const { mutateAsync: uploadFileMutation } = usePostUploadFileV2();

  const getFilesToUpload = async ({
    files,
  }: {
    files?: File[];
  }): Promise<File[]> => {
    if (!files) {
      files = await createFileUpload({
        accept: types?.map((type) => `.${type}`).join(",") ?? "",
        multiple: true,
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
        // Check if file extension is allowed
        const fileExtension = file.name.split(".").pop()?.toLowerCase();
        if (types && (!fileExtension || !types.includes(fileExtension))) {
          throw new Error(
            `File type not allowed. Allowed types: ${types.join(", ")}`,
          );
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
