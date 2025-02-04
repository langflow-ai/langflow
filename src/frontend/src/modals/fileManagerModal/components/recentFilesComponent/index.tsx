import { Input } from "@/components/ui/input";
import { sortByBoolean, sortByDate } from "@/pages/MainPage/utils/sort-flows";
import { FileType } from "@/types/file_management";
import Fuse from "fuse.js";
import { useEffect, useMemo, useState } from "react";
import FilesRendererComponent from "../filesRendererComponent";

export default function RecentFilesComponent({
  files,
  selectedFiles,
  setSelectedFiles,
}: {
  selectedFiles: string[];
  files: FileType[];
  setSelectedFiles: (files: string[]) => void;
}) {
  const [fuse, setFuse] = useState<Fuse<FileType>>(new Fuse([]));

  useEffect(() => {
    if (files) {
      setFuse(
        new Fuse(files, {
          keys: ["name"],
          threshold: 0.3,
        }),
      );
    }
  }, [files]);

  const [searchQuery, setSearchQuery] = useState("");

  const searchResults = useMemo(() => {
    if (!searchQuery) return files ?? [];
    return fuse.search(searchQuery).map(({ item }) => item);
  }, [searchQuery, files, selectedFiles]);

  const handleFileSelect = (fileId: string) => {
    setSelectedFiles(
      selectedFiles.includes(fileId)
        ? selectedFiles.filter((name) => name !== fileId)
        : [...selectedFiles, fileId],
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-6">
        <span className="text-sm font-medium">Recent Files</span>
        <div className="flex-1">
          <Input
            icon="Search"
            placeholder="Search files..."
            className=""
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>
      <div className="flex h-56 flex-col gap-1">
        <FilesRendererComponent
          files={searchResults
            .toSorted((a, b) => {
              const selectedOrder = sortByBoolean(
                selectedFiles.includes(a.id),
                selectedFiles.includes(b.id),
              );
              return selectedOrder === 0
                ? sortByDate(
                    a.updated_at ?? a.created_at,
                    b.updated_at ?? b.created_at,
                  )
                : selectedOrder;
            })
            .slice(0, 5)}
          handleFileSelect={handleFileSelect}
          selectedFiles={selectedFiles}
        />
      </div>
    </div>
  );
}
