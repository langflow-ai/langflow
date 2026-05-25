import { AnimatePresence, motion } from "framer-motion";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { ChatMessageType, ContentBlock } from "@/types/chat";
import { cn } from "@/utils/utils";
import { extractErrorMessage } from "../utils/extract-error-message";

interface ErrorViewProps {
  blocks: ContentBlock[];
  showError: boolean;
  lastMessage: boolean;
  closeChat?: () => void;
  fitViewNode: (id: string) => void;
  chat: ChatMessageType;
}

/**
 * Loading state shown while error is being processed.
 */
function ErrorLoadingState() {
  return (
    <motion.div
      key="loading"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex w-full gap-4 rounded-md p-2"
    >
      <div className="relative hidden h-6 w-6 flex-shrink-0 items-center justify-center overflow-hidden rounded bg-white text-2xl @[45rem]/chat-panel:!flex border-0">
        <div className="flex h-5 w-5 items-center justify-center">
          <ForwardedIconComponent
            name="Indicator"
            className="h-[6px] w-[6px] text-black"
          />
        </div>
      </div>
      <div className="flex items-center">
        <TextShimmer className="" duration={1}>
          Flow running...
        </TextShimmer>
      </div>
    </motion.div>
  );
}

interface ErrorAccordionProps {
  content: ContentBlock["contents"][number] & { type: "error" };
  chat: ChatMessageType;
  closeChat?: () => void;
  fitViewNode: (id: string) => void;
}

/**
 * Accordion component for displaying error details.
 */
function ErrorAccordion({
  content,
  chat,
  closeChat,
  fitViewNode,
}: ErrorAccordionProps) {
  const errorMessage = extractErrorMessage(content.reason) || content.component;
  const handleComponentClick = () => {
    fitViewNode(chat.properties?.source?.id ?? "");
    closeChat?.();
  };

  return (
    <Accordion type="single" collapsible className="w-full p-0">
      <AccordionItem value="error-details" className="border-0">
        <AccordionTrigger className="hover:no-underline [&>svg]:hidden p-0">
          <div className="flex flex-col gap-2 w-full">
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  className="h-[6px] w-[6px] text-destructive"
                  name="Indicator"
                />
                <span className="text-muted-foreground text-xs">
                  An error occurred
                </span>
              </div>
              <ForwardedIconComponent
                className="h-4 w-4 text-muted-foreground"
                name="ChevronsUpDown"
              />
            </div>
          </div>
        </AccordionTrigger>
        <AccordionContent className="pt-2">
          <div>
            {content.field && <p className="text-xs">Field: {content.field}</p>}
            {content.component && (
              <p
                className={cn(
                  closeChat ? "cursor-pointer underline text-xs" : "text-xs",
                )}
                onClick={closeChat ? handleComponentClick : undefined}
              >
                {errorMessage}
              </p>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

/**
 * Main error view component.
 */
export const ErrorView = ({
  closeChat,
  fitViewNode,
  chat,
  showError,
  lastMessage,
  blocks,
}: ErrorViewProps) => {
  const showLoading = !showError && lastMessage;

  return (
    <AnimatePresence mode="wait">
      {showLoading ? (
        <ErrorLoadingState />
      ) : (
        <div className="flex flex-col gap-2" data-testid="error-card-stack">
          {blocks.map((block, blockIndex) => (
            <div
              key={blockIndex}
              className="w-full rounded-md border border-border pt-[6px] pr-[6px] pb-[6px] pl-[8px] text-sm text-foreground"
              data-testid="error-card"
            >
              {block.contents.map((content, contentIndex) => {
                if (content.type === "error") {
                  return (
                    <ErrorAccordion
                      key={contentIndex}
                      content={content}
                      chat={chat}
                      closeChat={closeChat}
                      fitViewNode={fitViewNode}
                    />
                  );
                }
                return null;
              })}
            </div>
          ))}
        </div>
      )}
    </AnimatePresence>
  );
};
