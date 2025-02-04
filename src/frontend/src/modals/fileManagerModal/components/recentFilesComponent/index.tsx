import { Input } from "@/components/ui/input";
import { useGetFilesV2 } from "@/controllers/API/queries/file-management";
import { sortByDate } from "@/pages/MainPage/utils/sort-flows";
import { FileType } from "@/types/file_management";
import Fuse from "fuse.js";
import { useEffect, useMemo, useState } from "react";
import FilesRendererComponent from "../filesRendererComponent";

export default function RecentFilesComponent({
  selectedFiles,
  setSelectedFiles,
}: {
  selectedFiles: string[];
  setSelectedFiles: (files: string[]) => void;
}) {
  const { data: files } = useGetFilesV2();

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
    if (!searchQuery)
      return (
        files?.toSorted((a, b) =>
          sortByDate(
            a.updated_at ?? a.created_at,
            b.updated_at ?? b.created_at,
          ),
        ) ?? []
      );
    return fuse.search(searchQuery).map(({ item }) => item);
  }, [searchQuery, files]);

  const handleFileSelect = (fileName: string) => {
    setSelectedFiles(
      selectedFiles.includes(fileName)
        ? selectedFiles.filter((name) => name !== fileName)
        : [...selectedFiles, fileName],
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
          files={searchResults.slice(0, 5)}
          handleFileSelect={handleFileSelect}
          selectedFiles={selectedFiles}
        />
      </div>
    </div>
  );
}
