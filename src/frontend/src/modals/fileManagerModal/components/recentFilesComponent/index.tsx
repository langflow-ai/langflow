import { Input } from "@/components/ui/input";
import Fuse from "fuse.js";
import { useMemo, useState } from "react";
import FilesRendererComponent from "../filesRendererComponent";

export default function RecentFilesComponent({
  selectedFiles,
  setSelectedFiles,
}: {
  selectedFiles: string[];
  setSelectedFiles: (files: string[]) => void;
}) {
  const files = [
    {
      type: "json",
      name: "user_profile_data.json",
      size: "640 KB",
    },
    {
      type: "csv",
      name: "Q4_Reports.csv",
      size: "80 KB",
    },
    {
      type: "txt",
      name: "Highschool Speech.txt",
      size: "10 KB",
    },
    {
      type: "pdf",
      name: "logoconcepts.pdf",
      size: "1.2 MB",
    },
  ];

  const [searchQuery, setSearchQuery] = useState("");
  const fuse = new Fuse(files, {
    keys: ["name", "type"],
    threshold: 0.3,
  });

  const searchResults = useMemo(() => {
    if (!searchQuery) return files;
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
      <div className="flex h-44 flex-col gap-1">
        <FilesRendererComponent
          files={searchResults}
          handleFileSelect={handleFileSelect}
          selectedFiles={selectedFiles}
        />
      </div>
    </div>
  );
}
