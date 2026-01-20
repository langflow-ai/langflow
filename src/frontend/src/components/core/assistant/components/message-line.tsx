import type { AssistantMessage } from "../assistant.types";
import { ComponentResultLine } from "./component-result-line";
import { FailedComponentLine } from "./failed-component-line";
import { InputMessage } from "./input-message";
import { OutputMessage } from "./output-message";
import { ProgressLine } from "./progress-line";
import { SystemMessage } from "./system-message";
import { ValidationErrorMessage } from "./validation-error-message";

type MessageLineProps = {
  message: AssistantMessage;
  onAddToCanvas: (code: string) => Promise<void>;
};

export const MessageLine = ({ message, onAddToCanvas }: MessageLineProps) => {
  if (
    message.type === "validated" &&
    message.metadata?.componentCode &&
    message.metadata?.className
  ) {
    return (
      <ComponentResultLine
        className={message.metadata.className}
        code={message.metadata.componentCode}
        onAddToCanvas={onAddToCanvas}
      />
    );
  }

  if (message.type === "progress" && message.metadata?.progress) {
    if (message.metadata.progress.step === "validation_failed") {
      return (
        <FailedComponentLine
          componentName={message.metadata.progress.componentName}
          code={message.metadata.progress.componentCode}
          error={message.metadata.progress.error}
        />
      );
    }

    return (
      <ProgressLine
        content={message.content}
        progress={message.metadata.progress}
      />
    );
  }

  if (message.type === "validation_error") {
    return <ValidationErrorMessage />;
  }

  if (message.type === "output") {
    return <OutputMessage content={message.content} />;
  }

  if (message.type === "input") {
    return <InputMessage content={message.content} />;
  }

  return <SystemMessage content={message.content} type={message.type} />;
};
