import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import { Button } from "../../../../../../components/ui/button";

export default function DownloadButton({
  isHovered,
  handleDownload,
}: {
  isHovered: boolean;
  handleDownload: () => void;
}): JSX.Element | undefined {
  if (isHovered) {
    return (
      <div
        className={`bg-muted text-foreground absolute top-1 right-1 rounded-md text-sm font-bold`}
      >
        <Button
          unstyled
          className="text-ring bg-transparent px-2 py-1"
          onClick={handleDownload}
        >
          <ForwardedIconComponent
            name="DownloadCloud"
            className="h-5 w-5 bg-transparent text-current hover:scale-110"
          />
        </Button>
      </div>
    );
  }
  return undefined;
}
