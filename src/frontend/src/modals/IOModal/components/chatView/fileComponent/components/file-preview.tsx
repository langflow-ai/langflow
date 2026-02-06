import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../../components/common/genericIconComponent";
import { Skeleton } from "../../../../../../components/ui/skeleton";
import { Loading } from "@/components/ui/loading";
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
          <div className="flex h-20 w-20 items-center justify-center rounded-md border border-ring bg-background">
            <Loading size={40} className="text-primary" />
          </div>
        ) : (
          <div
            className={`relative ${
              isImage ? "h-20 w-20" : "h-20 w-80"
            } cursor-wait rounded-lg border border-ring bg-background transition duration-300`}
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
          } cursor-pointer rounded-lg border border-border bg-background transition duration-300 group-hover:shadow-md`}
        >
          {isImage ? (
            <img
              src={URL.createObjectURL(file)}
              alt="file"
              className="block h-full w-full rounded-md border border-border"
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
            className={`absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center opacity-100 transition-opacity`}
          >
            <div
              className="group flex h-7 w-7 cursor-pointer items-center justify-center rounded-full bg-muted p-2 transition-all hover:bg-input"
              onClick={onDelete}
            >
              <IconComponent
                name="X"
                className="h-4 w-4 stroke-muted-foreground stroke-2 group-hover:stroke-primary"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
