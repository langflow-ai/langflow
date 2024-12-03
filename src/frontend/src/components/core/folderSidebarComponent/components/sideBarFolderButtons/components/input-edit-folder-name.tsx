import { Input } from "@/components/ui/input";
import { FolderType } from "@/pages/MainPage/entities";

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
    folderName: string,
  ) => void;
  item: FolderType;
  refInput: React.RefObject<HTMLInputElement>;
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
  editFolderName: { name: string; edit: boolean };
  foldersNames: Record<string, string>;
}) => {
  return (
    <>
      <Input
        className="h-6 flex-1 focus:border-0"
        onChange={(e) => {
          handleEditFolderName(e, item.name);
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
          if (e.relatedTarget?.id === `options-trigger-${item.name}`) {
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
        value={foldersNames[item.name]}
        id={`input-folder-${item.name}`}
        data-testid={`input-folder`}
      />
    </>
  );
};
