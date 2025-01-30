import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import { useState } from "react";

export default function RecentFilesComponent() {
  const typeToIcon = {
    json: {
      icon: "file-json",
      color: "text-datatype-indigo dark:text-datatype-indigo-foreground",
    },
    csv: {
      icon: "file-chart-column",
      color: "text-datatype-emerald dark:text-datatype-emerald-foreground",
    },
    txt: {
      icon: "file-type",
      color: "text-datatype-purple dark:text-datatype-purple-foreground",
    },
    pdf: {
      icon: "file",
      color: "text-datatype-red dark:text-datatype-red-foreground",
    },
  };
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

  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);

  const handleFileSelect = (fileName: string) => {
    setSelectedFiles((prev) =>
      prev.includes(fileName)
        ? prev.filter((name) => name !== fileName)
        : [...prev, fileName],
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
        {files.map((file) => (
          <div
            key={file.name}
            className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 hover:bg-accent"
            onClick={() => handleFileSelect(file.name)}
          >
            <div className="flex items-center gap-4">
              <div className="flex" onClick={(e) => e.stopPropagation()}>
                <Checkbox
                  checked={selectedFiles.includes(file.name)}
                  onCheckedChange={() => handleFileSelect(file.name)}
                />
              </div>
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name={typeToIcon[file.type].icon}
                  className={cn(
                    "h-6 w-6 shrink-0",
                    typeToIcon[file.type].color,
                  )}
                />
                <span className="text-sm font-medium">{file.name}</span>
                <span className="text-xs text-muted-foreground">
                  {file.size}
                </span>
              </div>
            </div>
            <Button
              size="iconMd"
              variant="ghost"
              className="hover:bg-secondary-foreground/5"
              onClick={(e) => {
                e.stopPropagation();
                console.log("oiee");
              }}
            >
              <ForwardedIconComponent
                name="EllipsisVertical"
                className="h-5 w-5 shrink-0 text-muted-foreground"
              />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
