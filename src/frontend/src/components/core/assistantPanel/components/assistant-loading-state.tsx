import { memo, useEffect, useMemo, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import type { AgenticProgressState } from "@/controllers/API/queries/agentic";
import {
  getRandomReasoningHeader,
  getRandomReasoningMessages,
  getRandomValidationMessages,
} from "../helpers/messages";

interface AssistantLoadingStateProps {
  progress: AgenticProgressState;
  completedSteps: string[];
  onValidationComplete?: () => void;
}

const TYPING_SPEED = 30;
const MESSAGE_DELAY = 400;

function TypingCursor() {
  return (
    <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent-emerald-foreground/50" />
  );
}

function AssistantLoadingStateComponent({
  progress,
  onValidationComplete,
}: AssistantLoadingStateProps) {
  const [lines, setLines] = useState<string[]>([]);
  const [typingText, setTypingText] = useState("");
  const [typingIndex, setTypingIndex] = useState(0);
  const [isWaiting, setIsWaiting] = useState(false);

  // Generate randomized messages once per component instance
  const reasoningHeader = useMemo(() => getRandomReasoningHeader(), []);

  const reasoningMessages = useMemo(() => {
    const msgs = getRandomReasoningMessages();
    return [
      msgs.analyzing,
      msgs.identifyingInputs,
      msgs.checkingDependencies,
      msgs.generatingCode,
    ];
  }, []);

  const validationMessages = useMemo(() => getRandomValidationMessages(), []);

  const messageIndexRef = useRef(0);
  const hasFinishedReasoningRef = useRef(false);

  // Track which validation steps we've queued
  const queuedValidationStepsRef = useRef<Set<string>>(new Set());
  // Queue of validation messages to type
  const validationQueueRef = useRef<string[]>([]);
  // Currently typing a validation message
  const isTypingValidationRef = useRef(false);

  const isValidated = progress.step === "validated";
  const [validationTypingDone, setValidationTypingDone] = useState(false);

  // Get validation message for current step
  const getValidationMessage = (step: string) => {
    if (step === "validating") return validationMessages.validating;
    if (step === "validation_failed") return validationMessages.validationFailed;
    if (step === "retrying") return validationMessages.retrying;
    return null;
  };

  const currentValidationMessage = getValidationMessage(progress.step);

  // Queue validation messages as they arrive
  useEffect(() => {
    if (currentValidationMessage && !queuedValidationStepsRef.current.has(progress.step)) {
      queuedValidationStepsRef.current.add(progress.step);
      validationQueueRef.current.push(currentValidationMessage);

      // If we finished reasoning and not currently typing, trigger typing
      if (hasFinishedReasoningRef.current && !isTypingValidationRef.current) {
        setIsWaiting(false);
      }
    }
  }, [currentValidationMessage, progress.step]);

  // Handle fast validation - queue "Validating..." when validated arrives quickly
  useEffect(() => {
    if (isValidated && hasFinishedReasoningRef.current) {
      if (!queuedValidationStepsRef.current.has("validating")) {
        queuedValidationStepsRef.current.add("validating");
        validationQueueRef.current.push(validationMessages.validating);
        if (!isTypingValidationRef.current) {
          setIsWaiting(false);
        }
      }
    }
  }, [isValidated, validationMessages.validating]);

  // Show result only after validation message is fully typed (success or failure)
  useEffect(() => {
    if (validationTypingDone) {
      onValidationComplete?.();
    }
  }, [validationTypingDone, onValidationComplete]);

  // Handle typing animation
  useEffect(() => {
    // Determine current message to type
    let currentMessage: string | undefined;

    if (messageIndexRef.current < reasoningMessages.length) {
      // Still typing reasoning messages
      currentMessage = reasoningMessages[messageIndexRef.current];
    } else if (validationQueueRef.current.length > 0) {
      // Typing validation messages from queue
      isTypingValidationRef.current = true;
      currentMessage = validationQueueRef.current[0];
    } else {
      // Nothing to type
      hasFinishedReasoningRef.current = true;
      isTypingValidationRef.current = false;
      setIsWaiting(true);
      return;
    }

    if (!currentMessage) {
      hasFinishedReasoningRef.current = true;
      setIsWaiting(true);
      return;
    }

    // Type character by character
    if (typingIndex < currentMessage.length) {
      const timeout = setTimeout(() => {
        setTypingText(currentMessage!.slice(0, typingIndex + 1));
        setTypingIndex((prev) => prev + 1);
      }, TYPING_SPEED);
      return () => clearTimeout(timeout);
    }

    // Message complete - add to lines and move to next
    const timeout = setTimeout(() => {
      setLines((prev) => {
        if (prev.includes(currentMessage!)) return prev;
        return [...prev, currentMessage!];
      });
      setTypingText("");
      setTypingIndex(0);

      if (messageIndexRef.current < reasoningMessages.length) {
        // Move to next reasoning message
        messageIndexRef.current += 1;
        if (messageIndexRef.current >= reasoningMessages.length) {
          hasFinishedReasoningRef.current = true;
          // Check if there are validation messages queued
          if (validationQueueRef.current.length === 0) {
            setIsWaiting(true);
          }
        }
      } else if (validationQueueRef.current.length > 0) {
        // Remove the completed validation message from queue
        validationQueueRef.current.shift();

        if (validationQueueRef.current.length === 0) {
          // No more messages in queue
          isTypingValidationRef.current = false;
          setValidationTypingDone(true);
          setIsWaiting(true);
        }
        // Otherwise, the next iteration will pick up the next message
      }
    }, MESSAGE_DELAY);

    return () => clearTimeout(timeout);
  }, [typingIndex, isWaiting, currentValidationMessage, reasoningMessages]);

  return (
    <div className="rounded-lg border border-border bg-background">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border bg-muted/50 px-4 py-3 text-sm font-medium text-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>{reasoningHeader}</span>
      </div>

      {/* Messages */}
      <div className="flex flex-col gap-2 p-4">
        {lines.map((line, index) => {
          const isLastLine = index === lines.length - 1;
          const showCursorOnLastLine = isLastLine && !typingText && isWaiting;

          return (
            <div
              key={`${index}-${line}`}
              className="flex items-center gap-2 text-sm text-muted-foreground"
            >
              <span className="text-muted-foreground/60">›</span>
              <span>
                {line}
                {showCursorOnLastLine && <TypingCursor />}
              </span>
            </div>
          );
        })}

        {typingText && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="text-muted-foreground/60">›</span>
            <span>
              {typingText}
              <TypingCursor />
            </span>
          </div>
        )}

        {progress.attempt > 0 && (
          <div className="mt-2 text-xs text-muted-foreground">
            Attempt {progress.attempt} of {progress.maxAttempts}
          </div>
        )}
      </div>
    </div>
  );
}

export const AssistantLoadingState = memo(AssistantLoadingStateComponent);
export default AssistantLoadingState;
