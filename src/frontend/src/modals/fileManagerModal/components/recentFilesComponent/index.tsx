import { Input } from "@/components/ui/input";
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
          <Input icon="Search" placeholder="Search files..." className="" />
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <FilesRendererComponent
          files={files}
          handleFileSelect={handleFileSelect}
          selectedFiles={selectedFiles}
        />
      </div>
    </div>
  );
}
