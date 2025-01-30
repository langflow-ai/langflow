import { ReactNode, useEffect, useState } from "react";
import { ForwardedIconComponent } from "../../components/common/genericIconComponent";
import BaseModal from "../baseModal";
import DragFilesComponent from "./components/dragFilesComponent";
import ImportFilesComponent from "./components/importFilesComponent";
import RecentFilesComponent from "./components/recentFilesComponent";

export default function FileManagerModal({
  children,
  open,
  handleSubmit,
  setOpen,
  disabled,
}: {
  children?: ReactNode;
  open?: boolean;
  handleSubmit: (files: String[]) => void;
  setOpen?: (open: boolean) => void;
  disabled?: boolean;
}): JSX.Element {
  const [internalOpen, internalSetOpen] = useState(open);

  useEffect(() => {
    internalSetOpen(open);
  }, [open]);

  const [selectedFiles, setSelectedFiles] = useState<String[]>([]);

  return (
    <>
      <BaseModal
        size="smaller-h-full"
        open={!disabled && internalOpen}
        setOpen={internalSetOpen}
        onSubmit={() => {
          handleSubmit(selectedFiles);
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
            File Manager
          </span>
        </BaseModal.Header>
        <BaseModal.Content>
          <div className="flex flex-col gap-4">
            <DragFilesComponent />
            <ImportFilesComponent />
            <RecentFilesComponent />
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
