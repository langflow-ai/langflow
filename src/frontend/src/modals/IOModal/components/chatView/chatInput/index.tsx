import { useState } from "react";
import ShortUniqueId from "short-unique-id";
import IconComponent from "../../../../../components/genericIconComponent";
import { Textarea } from "../../../../../components/ui/textarea";
import {
  CHAT_INPUT_PLACEHOLDER,
  CHAT_INPUT_PLACEHOLDER_SEND,
} from "../../../../../constants/constants";
import { uploadFile } from "../../../../../controllers/API";
import { Case } from "../../../../../shared/components/caseComponent";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import {
  FilePreviewType,
  chatInputType,
} from "../../../../../types/components";
import { classNames } from "../../../../../utils/utils";
import FilePreview from "../filePreviewChat";
import useAutoResizeTextArea from "./hooks/use-auto-resize-text-area";
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
  const uid = new ShortUniqueId({ length: 3 });
  const [files, setFiles] = useState<FilePreviewType[]>([]);

  useFocusOnUnlock(lockChat, inputRef);
  useAutoResizeTextArea(chatValue, inputRef);
  useUpload(uploadFile, currentFlowId, setFiles, uid);

  const send = () => {
    sendMessage({
      repeat,
      files: files.map((file) => file.path ?? "").filter((file) => file !== ""),
    });
    setFiles([]);
  };

  return (
    <div className="flex w-full flex-col-reverse">
      <div className="relative w-full">
        <Textarea
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !lockChat &&
              !saveLoading &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              send();
            }
          }}
          rows={1}
          ref={inputRef}
          disabled={lockChat || noInput || saveLoading}
          style={{
            resize: "none",
            bottom: `${inputRef?.current?.scrollHeight}px`,
            maxHeight: "150px",
            overflow: `${
              inputRef.current && inputRef.current.scrollHeight > 150
                ? "auto"
                : "hidden"
            }`,
          }}
          value={
            lockChat ? "Thinking..." : saveLoading ? "Saving..." : chatValue
          }
          onChange={(event): void => {
            setChatValue(event.target.value);
          }}
          className={classNames(
            lockChat || saveLoading
              ? " form-modal-lock-true bg-input"
              : noInput
                ? "form-modal-no-input bg-input"
                : " form-modal-lock-false bg-background",

            "form-modal-lockchat",
          )}
          placeholder={
            noInput ? CHAT_INPUT_PLACEHOLDER : CHAT_INPUT_PLACEHOLDER_SEND
          }
        />
        <div className="form-modal-send-icon-position">
          <button
            className={classNames(
              "form-modal-send-button",
              noInput
                ? "bg-high-indigo text-background"
                : chatValue === ""
                  ? "text-primary"
                  : "bg-chat-send text-background",
            )}
            disabled={lockChat || saveLoading}
            onClick={(): void => send()}
          >
            <Case condition={lockChat || saveLoading}>
              <IconComponent
                name="Lock"
                className="form-modal-lock-icon"
                aria-hidden="true"
              />
            </Case>

            <Case condition={noInput}>
              <IconComponent
                name="Zap"
                className="form-modal-play-icon"
                aria-hidden="true"
              />
            </Case>

            <Case condition={!(lockChat || saveLoading) && !noInput}>
              <IconComponent
                name="LucideSend"
                className="form-modal-send-icon "
                aria-hidden="true"
              />
            </Case>
          </button>
        </div>
      </div>
      <div className="flex w-full gap-2 pb-2">
        {files.map((file) => (
          <FilePreview
            error={file.error}
            file={file.file}
            loading={file.loading}
            key={file.id}
            onDelete={() => {
              setFiles((prev) => prev.filter((f) => f.id !== file.id));
            }}
          />
        ))}
      </div>
    </div>
  );
}
