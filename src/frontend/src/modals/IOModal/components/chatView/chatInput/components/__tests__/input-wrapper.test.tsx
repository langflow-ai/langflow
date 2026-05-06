import { render, screen } from "@testing-library/react";
import React from "react";
import InputWrapper from "../input-wrapper";

jest.mock("@/customization/feature-flags", () => ({
  __esModule: true,
  get ENABLE_FILES_ON_PLAYGROUND() {
    return mockFlags.ENABLE_FILES_ON_PLAYGROUND;
  },
  get ENABLE_VOICE_ASSISTANT() {
    return mockFlags.ENABLE_VOICE_ASSISTANT;
  },
}));

jest.mock("@/controllers/API/queries/config/use-get-config", () => ({
  useGetConfig: () => ({ data: { voice_mode_available: mockVoiceAvailable } }),
}));

const mockFlags = {
  ENABLE_FILES_ON_PLAYGROUND: false,
  ENABLE_VOICE_ASSISTANT: false,
};
let mockVoiceAvailable = false;

beforeEach(() => {
  mockFlags.ENABLE_FILES_ON_PLAYGROUND = false;
  mockFlags.ENABLE_VOICE_ASSISTANT = false;
  mockVoiceAvailable = false;
});

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("../upload-file-button", () => ({
  __esModule: true,
  default: () => <div data-testid="upload-file-button" />,
}));

jest.mock("../button-send-wrapper", () => ({
  __esModule: true,
  default: () => <div data-testid="send-button" />,
}));

jest.mock("../voice-assistant/components/voice-button", () => ({
  __esModule: true,
  default: () => <div data-testid="voice-button" />,
}));

jest.mock("../../../fileComponent/components/file-preview", () => ({
  __esModule: true,
  default: () => <div data-testid="file-preview" />,
}));

jest.mock("../text-area-wrapper", () => ({
  __esModule: true,
  default: () => <textarea data-testid="text-area" />,
}));

const renderWrapper = () => {
  const inputRef = React.createRef<HTMLTextAreaElement>();
  const fileInputRef = React.createRef<HTMLInputElement>();
  return render(
    <InputWrapper
      isBuilding={false}
      checkSendingOk={() => false}
      send={() => {}}
      noInput={false}
      chatValue=""
      inputRef={inputRef as React.RefObject<HTMLTextAreaElement>}
      files={[]}
      isDragging={false}
      handleDeleteFile={() => {}}
      fileInputRef={fileInputRef}
      handleFileChange={() => {}}
      handleButtonClick={() => {}}
      setShowAudioInput={() => {}}
      currentFlowId="flow-1"
      playgroundPage={true}
    />,
  );
};

const dispatchOn = (
  element: Element,
  type: string,
  init: KeyboardEventInit | MouseEventInit,
) => {
  const event =
    type === "keydown"
      ? new KeyboardEvent(type, { bubbles: true, cancelable: true, ...init })
      : new MouseEvent(type, { bubbles: true, cancelable: true, ...init });
  const preventDefaultSpy = jest.spyOn(event, "preventDefault");
  const stopPropagationSpy = jest.spyOn(event, "stopPropagation");
  element.dispatchEvent(event);
  return { preventDefaultSpy, stopPropagationSpy };
};

describe("IOModal chat input wrapper", () => {
  it("should_not_prevent_default_when_space_is_pressed_inside_textarea", () => {
    renderWrapper();
    const textarea = screen.getByTestId("text-area");

    const { preventDefaultSpy } = dispatchOn(textarea, "keydown", { key: " " });

    expect(preventDefaultSpy).not.toHaveBeenCalled();
  });

  it("should_not_prevent_default_when_enter_is_pressed_inside_textarea", () => {
    renderWrapper();
    const textarea = screen.getByTestId("text-area");

    const { preventDefaultSpy } = dispatchOn(textarea, "keydown", {
      key: "Enter",
    });

    expect(preventDefaultSpy).not.toHaveBeenCalled();
  });

  it("should_not_prevent_default_when_other_key_is_pressed_inside_textarea", () => {
    renderWrapper();
    const textarea = screen.getByTestId("text-area");

    const { preventDefaultSpy } = dispatchOn(textarea, "keydown", { key: "a" });

    expect(preventDefaultSpy).not.toHaveBeenCalled();
  });

  it("should_prevent_default_and_move_cursor_to_end_when_space_is_pressed_outside_textarea", () => {
    const inputRef = React.createRef<HTMLTextAreaElement>();
    const fileInputRef = React.createRef<HTMLInputElement>();
    const realTextarea = document.createElement("textarea");
    realTextarea.value = "abc";
    (inputRef as { current: HTMLTextAreaElement | null }).current =
      realTextarea;
    const selectionSpy = jest.spyOn(realTextarea, "setSelectionRange");

    render(
      <InputWrapper
        isBuilding={false}
        checkSendingOk={() => false}
        send={() => {}}
        noInput={false}
        chatValue="abc"
        inputRef={inputRef as React.RefObject<HTMLTextAreaElement>}
        files={[]}
        isDragging={false}
        handleDeleteFile={() => {}}
        fileInputRef={fileInputRef}
        handleFileChange={() => {}}
        handleButtonClick={() => {}}
        setShowAudioInput={() => {}}
        currentFlowId="flow-1"
        playgroundPage={true}
      />,
    );
    const wrapper = screen.getByTestId("input-wrapper");

    const { preventDefaultSpy } = dispatchOn(wrapper, "keydown", { key: " " });

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(selectionSpy).toHaveBeenCalledWith(3, 3);
  });

  it("should_not_prevent_default_on_unrelated_key_outside_textarea", () => {
    renderWrapper();
    const wrapper = screen.getByTestId("input-wrapper");

    const { preventDefaultSpy } = dispatchOn(wrapper, "keydown", { key: "a" });

    expect(preventDefaultSpy).not.toHaveBeenCalled();
  });

  it("should_skip_focus_handling_when_mousedown_target_is_textarea", () => {
    renderWrapper();
    const textarea = screen.getByTestId("text-area");

    const { preventDefaultSpy, stopPropagationSpy } = dispatchOn(
      textarea,
      "mousedown",
      {},
    );

    expect(preventDefaultSpy).not.toHaveBeenCalled();
    expect(stopPropagationSpy).not.toHaveBeenCalled();
  });

  it("should_prevent_default_and_stop_propagation_on_mousedown_outside_textarea", () => {
    renderWrapper();
    const wrapper = screen.getByTestId("input-wrapper");

    const { preventDefaultSpy, stopPropagationSpy } = dispatchOn(
      wrapper,
      "mousedown",
      {},
    );

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(stopPropagationSpy).toHaveBeenCalled();
  });

  it("should_focus_input_when_wrapper_is_clicked_outside_textarea", () => {
    const inputRef = React.createRef<HTMLTextAreaElement>();
    const fileInputRef = React.createRef<HTMLInputElement>();
    const realTextarea = document.createElement("textarea");
    realTextarea.value = "hi";
    (inputRef as { current: HTMLTextAreaElement | null }).current =
      realTextarea;
    const focusSpy = jest.spyOn(realTextarea, "focus");
    const selectionSpy = jest.spyOn(realTextarea, "setSelectionRange");

    render(
      <InputWrapper
        isBuilding={false}
        checkSendingOk={() => false}
        send={() => {}}
        noInput={false}
        chatValue="hi"
        inputRef={inputRef as React.RefObject<HTMLTextAreaElement>}
        files={[]}
        isDragging={false}
        handleDeleteFile={() => {}}
        fileInputRef={fileInputRef}
        handleFileChange={() => {}}
        handleButtonClick={() => {}}
        setShowAudioInput={() => {}}
        currentFlowId="flow-1"
        playgroundPage={true}
      />,
    );
    const wrapper = screen.getByTestId("input-wrapper");

    dispatchOn(wrapper, "click", {});

    expect(focusSpy).toHaveBeenCalled();
    expect(selectionSpy).toHaveBeenCalledWith(2, 2);
  });

  it("should_render_voice_button_when_voice_assistant_is_enabled_and_available", () => {
    mockFlags.ENABLE_VOICE_ASSISTANT = true;
    mockVoiceAvailable = true;
    renderWrapper();

    expect(screen.getByTestId("voice-button")).toBeInTheDocument();
  });

  it("should_render_upload_button_when_not_on_playground_page", () => {
    const inputRef = React.createRef<HTMLTextAreaElement>();
    const fileInputRef = React.createRef<HTMLInputElement>();
    render(
      <InputWrapper
        isBuilding={false}
        checkSendingOk={() => false}
        send={() => {}}
        noInput={false}
        chatValue=""
        inputRef={inputRef as React.RefObject<HTMLTextAreaElement>}
        files={[]}
        isDragging={false}
        handleDeleteFile={() => {}}
        fileInputRef={fileInputRef}
        handleFileChange={() => {}}
        handleButtonClick={() => {}}
        setShowAudioInput={() => {}}
        currentFlowId="flow-1"
        playgroundPage={false}
      />,
    );

    expect(screen.getByTestId("upload-file-button")).toBeInTheDocument();
  });

  it("should_skip_focus_handling_when_click_target_is_textarea", () => {
    const inputRef = React.createRef<HTMLTextAreaElement>();
    const fileInputRef = React.createRef<HTMLInputElement>();
    const realTextarea = document.createElement("textarea");
    (inputRef as { current: HTMLTextAreaElement | null }).current =
      realTextarea;
    const focusSpy = jest.spyOn(realTextarea, "focus");

    render(
      <InputWrapper
        isBuilding={false}
        checkSendingOk={() => false}
        send={() => {}}
        noInput={false}
        chatValue=""
        inputRef={inputRef as React.RefObject<HTMLTextAreaElement>}
        files={[]}
        isDragging={false}
        handleDeleteFile={() => {}}
        fileInputRef={fileInputRef}
        handleFileChange={() => {}}
        handleButtonClick={() => {}}
        setShowAudioInput={() => {}}
        currentFlowId="flow-1"
        playgroundPage={true}
      />,
    );
    const textarea = screen.getByTestId("text-area");

    dispatchOn(textarea, "click", {});

    expect(focusSpy).not.toHaveBeenCalled();
  });
});
