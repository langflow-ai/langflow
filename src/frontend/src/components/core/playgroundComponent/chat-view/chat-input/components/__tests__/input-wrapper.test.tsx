import React from "react";
import { render, screen } from "@testing-library/react";
import InputWrapper from "../input-wrapper";

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_FILES_ON_PLAYGROUND: false,
}));

jest.mock("../upload-file-button", () => ({
  __esModule: true,
  default: () => <div data-testid="upload-file-button" />,
}));

jest.mock("../audio-button", () => ({
  __esModule: true,
  default: () => <div data-testid="audio-button" />,
}));

jest.mock("../button-send-wrapper", () => ({
  __esModule: true,
  default: () => <div data-testid="send-button" />,
}));

jest.mock("../text-area-wrapper", () => ({
  __esModule: true,
  default: () => <textarea data-testid="text-area" />,
}));

describe("Playground chat input wrapper", () => {
  it("hides the upload icon when the flag is false", () => {
    const inputRef = React.createRef<HTMLTextAreaElement>();
    const fileInputRef = React.createRef<HTMLInputElement>();

    render(
      <InputWrapper
        isBuilding={false}
        checkSendingOk={() => true}
        send={() => {}}
        noInput={false}
        chatValue="hello"
        inputRef={inputRef}
        files={[]}
        isDragging={false}
        handleDeleteFile={() => {}}
        fileInputRef={fileInputRef}
        handleFileChange={() => {}}
        handleButtonClick={() => {}}
        audioRecordingState="idle"
        onStartRecording={() => {}}
        onStopRecording={() => {}}
        isAudioSupported={false}
      />,
    );

    expect(screen.queryByTestId("upload-file-button")).not.toBeInTheDocument();
  });
});
