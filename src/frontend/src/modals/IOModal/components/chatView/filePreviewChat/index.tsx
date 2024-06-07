import { useState } from "react";
import IconComponent from "../../../../../components/genericIconComponent";
import LoadingComponent from "../../../../../components/loadingComponent";

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
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div className="relative inline-block w-56">
      {loading && <LoadingComponent remSize={5} />}
      {error && <div>Error...</div>}
      <div
        className={`relative overflow-hidden rounded-md bg-background p-4 transition duration-300 ${
          isHovered ? "shadow-md" : ""
        }`}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <img
          src={URL.createObjectURL(file)}
          alt="file"
          className="block h-auto w-full"
        />
        {isHovered && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-30">
            <div
              className="cursor-pointer rounded-full bg-white bg-opacity-80 p-2"
              onClick={onDelete}
            >
              <IconComponent name="trash" className="stroke-red-500" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
