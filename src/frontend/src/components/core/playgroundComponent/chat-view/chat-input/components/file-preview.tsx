import ForwardedIconComponent from "@/components/common/genericIconComponent";
import Loading from "@/components/ui/loading";
import { cn } from "@/utils/utils";

interface FilePreviewProps {
  file: File;
  loading: boolean;
  error: boolean;
  onDelete: () => void;
}

const FilePreview = ({ file, loading, error, onDelete }: FilePreviewProps) => {
  const isImage = file.type.startsWith("image/");

  return (
    <div
      className={cn(
        "relative flex h-16 w-16 items-center justify-center rounded-md border bg-muted",
        error && "border-error",
      )}
    >
      {loading ? (
        <Loading className="h-4 w-4" />
      ) : isImage ? (
        <img
          src={URL.createObjectURL(file)}
          alt={file.name}
          className="h-full w-full rounded-md object-cover"
        />
      ) : (
        <ForwardedIconComponent name="File" className="h-6 w-6" />
      )}

      <button
        onClick={onDelete}
        className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground hover:bg-destructive/90"
        type="button"
      >
        <ForwardedIconComponent name="X" className="h-3 w-3" />
      </button>
    </div>
  );
};

export default FilePreview;
