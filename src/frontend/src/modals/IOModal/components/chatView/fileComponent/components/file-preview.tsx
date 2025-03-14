import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../../components/common/genericIconComponent";
import { Skeleton } from "../../../../../../components/ui/skeleton";
import formatFileName from "../utils/format-file-name";

const supImgFiles = ["png", "jpg", "jpeg", "gif", "bmp", "webp", "image"];

export default function FilePreview({
  error,
  file,
  loading,
  onDelete,
}: {
  loading: boolean;
  file: File;
  error: boolean;
  onDelete: () => void;
}) {
  const fileType = file.type.toLowerCase();
  const isImage = supImgFiles.some((type) => fileType.includes(type));

  return (
    <div className="group relative pb-2">
      {loading ? (
        isImage ? (
          <div className="border-ring bg-background flex h-20 w-20 items-center justify-center rounded-md border">
            <svg
              aria-hidden="true"
              className={`text-muted h-10 w-10 animate-spin fill-black`}
              viewBox="0 0 100 101"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                fill="currentColor"
              />
              <path
                d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                fill="currentFill"
              />
            </svg>
          </div>
        ) : (
          <div
            className={`relative ${
              isImage ? "h-20 w-20" : "h-20 w-80"
            } border-ring bg-background cursor-wait rounded-lg border transition duration-300`}
          >
            <div className="ml-3 flex h-full w-full items-center gap-2 text-sm">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div className="flex flex-col gap-1">
                <Skeleton className="h-3 w-48" />
                <Skeleton className="h-3 w-10" />
              </div>
            </div>
          </div>
        )
      ) : error ? (
        <div>Error...</div>
      ) : (
        <div
          className={`relative mt-2 ${
            isImage ? "h-20 w-32" : "h-20 w-32"
          } border-border bg-background cursor-pointer rounded-lg border transition duration-300 group-hover:shadow-md`}
        >
          {isImage ? (
            <img
              src={URL.createObjectURL(file)}
              alt="file"
              className="border-border block h-full w-full rounded-md border"
            />
          ) : (
            <div className="ml-3 flex h-full w-full items-center gap-2 text-sm">
              <ForwardedIconComponent name="File" className="h-8 w-8" />
              <div className="flex flex-col">
                <span className="font-bold">{formatFileName(file.name)}</span>
                <span>File</span>
              </div>
            </div>
          )}
          <div
            className={`absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center opacity-100 transition-opacity`}
          >
            <div
              className="group bg-muted hover:bg-input flex h-7 w-7 cursor-pointer items-center justify-center rounded-full p-2 transition-all"
              onClick={onDelete}
            >
              <IconComponent
                name="X"
                className="stroke-muted-foreground group-hover:stroke-primary h-4 w-4 stroke-2"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
