import { useState } from "react";
import {
  CHAT_INPUT_PLACEHOLDER,
  CHAT_INPUT_PLACEHOLDER_SEND,
} from "../../../../../constants/constants";
import { uploadFile } from "../../../../../controllers/API";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import {
  FilePreviewType,
  chatInputType,
} from "../../../../../types/components";
import FilePreview from "../filePreviewChat";
import ButtonSendWrapper from "./components/buttonSendWrapper";
import TextAreaWrapper from "./components/textAreaWrapper";
import { getClassNamesFilePreview } from "./helpers/get-class-file-preview";
import useAutoResizeTextArea from "./hooks/use-auto-resize-text-area";
import useDragAndDrop from "./hooks/use-drag-and-drop";
import useFocusOnUnlock from "./hooks/use-focus-unlock";
import useUpload from "./hooks/use-upload";
export default function ChatInput({
  lockChat,
  chatValue,
  sendMessage,
  setChatValue,
  inputRef,
  noInput,
}: chatInputType): JSX.Element {
  const [repeat, setRepeat] = useState(1);
  const saveLoading = useFlowsManagerStore((state) => state.saveLoading);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [inputFocus, setInputFocus] = useState<boolean>(false);

  useFocusOnUnlock(lockChat, inputRef);
  useAutoResizeTextArea(chatValue, inputRef);
  useUpload(uploadFile, currentFlowId, setFiles);

  const { dragOver, dragEnter, dragLeave, onDrop } = useDragAndDrop(
    setIsDragging,
    setFiles,
    currentFlowId
  );

  const send = () => {
    sendMessage({
      repeat,
      files: files.map((file) => file.path ?? "").filter((file) => file !== ""),
    });
    setFiles([]);
  };

  const checkSendingOk = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    return (
      event.key === "Enter" &&
      !lockChat &&
      !saveLoading &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    );
  };

  const classNameFilePreview = getClassNamesFilePreview(inputFocus);

  return (
    <div className="flex w-full flex-col-reverse">
      <div className="relative w-full">
        <TextAreaWrapper
          dragOver={dragOver}
          dragEnter={dragEnter}
          dragLeave={dragLeave}
          onDrop={onDrop}
          checkSendingOk={checkSendingOk}
          send={send}
          lockChat={lockChat}
          noInput={noInput}
          saveLoading={saveLoading}
          chatValue={chatValue}
          setChatValue={setChatValue}
          CHAT_INPUT_PLACEHOLDER={CHAT_INPUT_PLACEHOLDER}
          CHAT_INPUT_PLACEHOLDER_SEND={CHAT_INPUT_PLACEHOLDER_SEND}
          inputRef={inputRef}
          setInputFocus={setInputFocus}
          files={files}
        />

        <div className="form-modal-send-icon-position">
          <ButtonSendWrapper
            send={send}
            lockChat={lockChat}
            noInput={noInput}
            saveLoading={saveLoading}
            chatValue={chatValue}
          />
        </div>
      </div>
      {files.length > 0 && (
        <div className={classNameFilePreview}>
          {files.map((file) => (
            <FilePreview
              error={file.error}
              file={file.file}
              loading={file.loading}
              key={file.id}
              onDelete={() => {
                setFiles((prev) => prev.filter((f) => f.id !== file.id));
                // TODO: delete file on backend
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
