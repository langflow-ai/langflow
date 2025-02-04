import { usePostUploadFileV2 } from "@/controllers/API/queries/file-management/use-post-upload-file";
import { createFileUpload } from "@/helpers/create-file-upload";

const useUploadFile = () => {
  const { mutateAsync: uploadFileMutation } = usePostUploadFileV2();

  const getFilesToUpload = async ({
    files,
  }: {
    files?: File[];
  }): Promise<File[]> => {
    if (!files) {
      files = await createFileUpload();
    }
    return files;
  };

  const uploadFile = async ({ files }: { files?: File[] }): Promise<void> => {
    try {
      const filesToUpload = await getFilesToUpload({ files });

      for (const file of filesToUpload) {
        await uploadFileMutation({
          file,
        });
      }
    } catch (e) {
      throw e;
    }
  };

  return uploadFile;
};

export default useUploadFile;
