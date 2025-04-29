"use client";

import { useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export const AddFolderButton = ({
  onClick,
  disabled,
  loading,
}: {
  onClick: (folderName: string) => void;  // Update: accept folder name
  disabled: boolean;
  loading: boolean;
}) => {
  const [open, setOpen] = useState(false);
  const [folderName, setFolderName] = useState(""); // State to store input

  const handleButtonClick = () => {
    setOpen(true);
  };

  const handleCreateFolder = () => {
    if (folderName.trim()) {
      onClick(folderName); 
      setFolderName("");   
      setOpen(false);      
    }
  };

  return (
    <>
      <ShadTooltip content="Create new folder" styleClasses="z-50">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 border-0 text-zinc-500 hover:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
          onClick={handleButtonClick}
          data-testid="add-folder-button"
          disabled={disabled}
          loading={loading}
        >
          <IconComponent name="Plus" className="h-4 w-4" />
        </Button>
      </ShadTooltip>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Create New Folder</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <input
              type="text"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreateFolder(); 
              }}
              placeholder="Enter Folder Name"
              className="w-full p-2 border rounded"
            />
            <button
              className="mt-2 w-full bg-primary hover:bg-primary-hover text-white p-2 rounded"
              onClick={handleCreateFolder}
            >
              Create
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
