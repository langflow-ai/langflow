import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { ENABLE_VOICE_ASSISTANT } from "@/customization/feature-flags";
import type { FilePreviewType } from "@/types/components";
import FilePreviewDisplay from "../../utils/file-preview-display";
import type { AudioRecordingState } from "../hooks/use-audio-recording";
import AudioButton from "./audio-button";
import ButtonSendWrapper from "./button-send-wrapper";
import TextAreaWrapper from "./text-area-wrapper";
import UploadFileButton from "./upload-file-button";

interface InputWrapperProps {
  isBuilding: boolean;
  checkSendingOk: (event: React.KeyboardEvent<HTMLTextAreaElement>) => boolean;
  send: () => void;
  noInput: boolean;
  chatValue: string;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  files: FilePreviewType[];
  isDragging: boolean;
  handleDeleteFile: (file: FilePreviewType) => void;
  fileInputRef: React.RefObject<HTMLInputElement>;
  handleFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleButtonClick: () => void;
  audioRecordingState: AudioRecordingState;
  onStartRecording: () => void;
  onStopRecording: () => void;
  isAudioSupported: boolean;
}

const InputWrapper = ({
  isBuilding,
  checkSendingOk,
  send,
  noInput,
  chatValue,
  inputRef,
  files,
  isDragging,
  handleDeleteFile,
  fileInputRef,
  handleFileChange,
  handleButtonClick,
  audioRecordingState,
  onStartRecording,
  onStopRecording,
  isAudioSupported,
}: InputWrapperProps) => {
  const classNameFilePreview = `flex w-full items-center gap-2 py-2 overflow-auto`;

  const { data: config } = useGetConfig();

  const onClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest("textarea")) {
      return;
    }
    inputRef.current?.focus();
    inputRef.current?.setSelectionRange(
      inputRef.current.value.length,
      inputRef.current.value.length,
    );
  };

  const onMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest("textarea")) {
      return;
    }
    e.stopPropagation();
    e.preventDefault();
  };
  return (
    <div className="flex w-full flex-col">
      {/* Input container */}
      <div
        data-testid="input-wrapper"
        className="flex w-full flex-col gap-2 rounded-md border border-input bg-background p-3 hover:border-muted-foreground focus-within:border-primary"
        onClick={onClick}
        onMouseDown={onMouseDown}
      >
        {/* Text input area */}
        <div className="w-full pb-3">
          <TextAreaWrapper
            CHAT_INPUT_PLACEHOLDER={"Send a message"}
            isBuilding={isBuilding}
            checkSendingOk={checkSendingOk}
            send={send}
            noInput={noInput}
            chatValue={chatValue}
            inputRef={inputRef}
            files={files}
            isDragging={isDragging}
          />
        </div>

        {/* File preview section */}
        {files.length > 0 && (
          <div className={classNameFilePreview}>
            {files.map((file) => (
              <FilePreviewDisplay
                file={file.file}
                loading={file.loading}
                error={file.error}
                showDelete={true}
                onDelete={() => {
                  handleDeleteFile(file);
                }}
                variant="compact"
                key={file.id}
              />
            ))}
          </div>
        )}

        {/* Buttons row */}
        <div className="flex items-center justify-between w-full pt-3">
          <div className="flex-shrink-0">
            <UploadFileButton
              isBuilding={isBuilding}
              fileInputRef={fileInputRef}
              handleFileChange={handleFileChange}
              handleButtonClick={handleButtonClick}
            />
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <AudioButton
              isBuilding={isBuilding}
              recordingState={audioRecordingState}
              onStartRecording={onStartRecording}
              onStopRecording={onStopRecording}
              isSupported={isAudioSupported}
            />
            <ButtonSendWrapper
              send={send}
              noInput={noInput}
              chatValue={chatValue}
              files={files}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default InputWrapper;
