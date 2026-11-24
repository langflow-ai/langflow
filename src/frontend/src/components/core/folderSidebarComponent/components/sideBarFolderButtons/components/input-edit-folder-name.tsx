import { Input } from "@/components/ui/input";
import type { FolderType } from "@/pages/MainPage/entities";

export const InputEditFolderName = ({
  handleEditFolderName,
  item,
  refInput,
  handleKeyDownFn,
  handleKeyDown,
  handleEditNameFolder,
  editFolderName,
  foldersNames,
}: {
  handleEditFolderName: (
    e: React.ChangeEvent<HTMLInputElement>,
    folderId: string,
  ) => void;
  item: FolderType;
  refInput: React.RefObject<HTMLInputElement | null>;
  handleKeyDownFn: (
    e: React.KeyboardEvent<HTMLInputElement>,
    folder: FolderType,
  ) => void;
  handleKeyDown: (
    e: React.KeyboardEvent<HTMLInputElement>,
    key: string,
    folderName: string,
  ) => void;
  handleEditNameFolder: (item: FolderType) => void;
  editFolderName: { id: string; edit: boolean };
  foldersNames: Record<string, string>;
}) => {
  return (
    <>
      <Input
        className="h-6 flex-1 text-xs focus:border-0"
        onChange={(e) => {
          handleEditFolderName(e, item.id!);
        }}
        maxLength={38}
        ref={refInput}
        onKeyDown={(e) => {
          handleKeyDownFn(e, item);
          handleKeyDown(e, e.key, "");
        }}
        autoFocus={true}
        onBlur={(e) => {
          // fixes autofocus problem where cursor isn't present
          if (e.relatedTarget?.id === `options-trigger-${item.id}`) {
            refInput.current?.focus();
            return;
          }

          if (refInput.current?.value !== item.name) {
            handleEditNameFolder(item);
          } else {
            editFolderName.edit = false;
          }
          refInput.current?.blur();
        }}
        value={foldersNames[item.id!]}
        id={`input-project-${item.id}`}
        data-testid={`input-project`}
      />
    </>
  );
};
