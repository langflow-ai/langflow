import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  default: () => <button data-testid="upload-file-button">upload</button>,
}));

jest.mock("../button-send-wrapper", () => ({
  __esModule: true,
  default: () => <button data-testid="send-button">send</button>,
}));

jest.mock("../voice-assistant/components/voice-button", () => ({
  __esModule: true,
  default: () => <button data-testid="voice-button">voice</button>,
}));

jest.mock("../../../fileComponent/components/file-preview", () => ({
  __esModule: true,
  default: () => <div data-testid="file-preview" />,
}));

jest.mock("../text-area-wrapper", () => {
  const actual = jest.requireActual("react");
  return {
    __esModule: true,
    default: ({
      inputRef,
    }: {
      inputRef: React.RefObject<HTMLTextAreaElement>;
    }) => {
      const [value, setValue] = actual.useState("");
      return (
        <textarea
          data-testid="text-area"
          ref={inputRef}
          value={value}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
            setValue(e.target.value)
          }
        />
      );
    },
  };
});

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
    const textarea = inputRef.current as HTMLTextAreaElement;
    textarea.value = "abc";
    const selectionSpy = jest.spyOn(textarea, "setSelectionRange");
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
    const textarea = inputRef.current as HTMLTextAreaElement;
    textarea.value = "hi";
    const focusSpy = jest.spyOn(textarea, "focus");
    const selectionSpy = jest.spyOn(textarea, "setSelectionRange");
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

  it("should_not_prevent_default_when_space_is_pressed_from_nested_send_button", () => {
    renderWrapper();
    const sendButton = screen.getByTestId("send-button");

    const { preventDefaultSpy } = dispatchOn(sendButton, "keydown", {
      key: " ",
    });

    expect(preventDefaultSpy).not.toHaveBeenCalled();
  });

  it("should_not_prevent_default_when_enter_is_pressed_from_nested_upload_button", () => {
    mockFlags.ENABLE_FILES_ON_PLAYGROUND = true;
    renderWrapper();
    const uploadButton = screen.getByTestId("upload-file-button");

    const { preventDefaultSpy } = dispatchOn(uploadButton, "keydown", {
      key: "Enter",
    });

    expect(preventDefaultSpy).not.toHaveBeenCalled();
  });

  it("should_not_prevent_default_on_mousedown_from_nested_send_button", () => {
    renderWrapper();
    const sendButton = screen.getByTestId("send-button");

    const { preventDefaultSpy, stopPropagationSpy } = dispatchOn(
      sendButton,
      "mousedown",
      {},
    );

    expect(preventDefaultSpy).not.toHaveBeenCalled();
    expect(stopPropagationSpy).not.toHaveBeenCalled();
  });

  it("should_preserve_spaces_when_user_types_multi_word_input", async () => {
    const user = userEvent.setup();
    renderWrapper();
    const textarea = screen.getByTestId("text-area") as HTMLTextAreaElement;

    await user.click(textarea);
    await user.keyboard("a b c");

    expect(textarea.value).toBe("a b c");
  });

  it("should_not_steal_focus_when_click_originates_on_nested_send_button", () => {
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
    const sendButton = screen.getByTestId("send-button");

    dispatchOn(sendButton, "click", {});

    expect(focusSpy).not.toHaveBeenCalled();
  });
});
