import { FileType } from "@/types/file_management";
import { ReactNode, useEffect, useState } from "react";
import { ForwardedIconComponent } from "../../components/common/genericIconComponent";
import BaseModal from "../baseModal";
import DragFilesComponent from "./components/dragFilesComponent";
import RecentFilesComponent from "./components/recentFilesComponent";

export default function FileManagerModal({
  children,
  handleSubmit,
  selectedFiles,
  disabled,
  files,
  types,
  isList,
}: {
  children?: ReactNode;
  selectedFiles?: string[];
  open?: boolean;
  handleSubmit: (files: string[]) => void;
  setOpen?: (open: boolean) => void;
  disabled?: boolean;
  files: FileType[];
  types: string[];
  isList?: boolean;
}): JSX.Element {
  const [internalOpen, internalSetOpen] = useState(false);

  const [internalSelectedFiles, setInternalSelectedFiles] = useState<string[]>(
    selectedFiles || [],
  );

  useEffect(() => {
    setInternalSelectedFiles(selectedFiles || []);
  }, [internalOpen]);

  const handleUpload = (filesPaths: string[]) => {
    setInternalSelectedFiles(
      isList ? [...internalSelectedFiles, ...filesPaths] : [filesPaths[0]],
    );
  };

  return (
    <>
      <BaseModal
        size="smaller-h-full"
        open={!disabled && internalOpen}
        setOpen={internalSetOpen}
        onSubmit={() => {
          handleSubmit(internalSelectedFiles);
          internalSetOpen(false);
        }}
      >
        <BaseModal.Trigger asChild>
          {children ? children : <></>}
        </BaseModal.Trigger>
        <BaseModal.Header description={null}>
          <span className="flex items-center gap-2 font-medium">
            <div className="rounded-md bg-muted p-1.5">
              <ForwardedIconComponent name="File" className="h-5 w-5" />
            </div>
            My Files
          </span>
        </BaseModal.Header>
        <BaseModal.Content>
          <div className="flex flex-col gap-4">
            <DragFilesComponent
              onUpload={handleUpload}
              types={types}
              isList={isList ?? false}
            />
            <RecentFilesComponent
              files={files}
              selectedFiles={internalSelectedFiles}
              setSelectedFiles={setInternalSelectedFiles}
              types={types}
              isList={isList ?? false}
            />
          </div>
        </BaseModal.Content>

        <BaseModal.Footer
          submit={{
            label: `Select files`,
            dataTestId: "select-files-modal-button",
          }}
        ></BaseModal.Footer>
      </BaseModal>
    </>
  );
}
