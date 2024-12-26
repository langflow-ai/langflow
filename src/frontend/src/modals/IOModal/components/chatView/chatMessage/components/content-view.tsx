import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { cn } from "@/utils/utils";
import { AnimatePresence, motion } from "framer-motion";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CodeTabsComponent from "../../../../../../components/core/codeTabsComponent/ChatCodeTabComponent";
import LogoIcon from "./chat-logo-icon";

export const ErrorView = ({
  closeChat,
  fitViewNode,
  chat,
  showError,
  lastMessage,
  blocks,
}: {
  blocks: any;
  showError: boolean;
  lastMessage: boolean;
  closeChat?: () => void;
  fitViewNode: (id: string) => void;
  chat: any;
}) => {
  return (
    <>
      <div className="w-5/6 max-w-[768px] py-4 word-break-break-word">
        <AnimatePresence mode="wait">
          {!showError && lastMessage ? (
            <motion.div
              key="loading"
              initial={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex w-full gap-4 rounded-md p-2"
            >
              <LogoIcon />
              <div className="flex items-center">
                <TextShimmer className="" duration={1}>
                  Flow running...
                </TextShimmer>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
              className="flex w-full gap-4 rounded-md p-2"
            >
              <LogoIcon />
              {blocks.map((block, blockIndex) => (
                <div
                  key={blockIndex}
                  className="w-full rounded-xl border border-error-red-border bg-error-red p-4 text-[14px] text-foreground"
                >
                  {block.contents.map((content, contentIndex) => {
                    if (content.type === "error") {
                      return (
                        <div className="" key={contentIndex}>
                          <div className="mb-2 flex items-center">
                            <ForwardedIconComponent
                              className="mr-2 h-[18px] w-[18px] text-destructive"
                              name="OctagonAlert"
                            />
                            {content.component && (
                              <>
                                <span>
                                  An error occured in the{" "}
                                  <span
                                    className={cn(
                                      closeChat ?? "cursor-pointer underline",
                                    )}
                                    onClick={() => {
                                      fitViewNode(
                                        chat.properties?.source?.id ?? "",
                                      );
                                      closeChat?.();
                                    }}
                                  >
                                    <strong>{content.component}</strong>
                                  </span>{" "}
                                  Component, stopping your flow. See below for
                                  more details.
                                </span>
                              </>
                            )}
                          </div>
                          <div>
                            <h3 className="pb-3 font-semibold">
                              Error details:
                            </h3>
                            {content.field && (
                              <p className="pb-1">Field: {content.field}</p>
                            )}
                            {content.reason && (
                              <span className="">
                                <Markdown
                                  linkTarget="_blank"
                                  remarkPlugins={[remarkGfm]}
                                  components={{
                                    a: ({ node, ...props }) => (
                                      <a
                                        href={props.href}
                                        target="_blank"
                                        className="underline"
                                        rel="noopener noreferrer"
                                      >
                                        {props.children}
                                      </a>
                                    ),
                                    p({ node, ...props }) {
                                      return (
                                        <span className="inline-block w-fit max-w-full">
                                          {props.children}
                                        </span>
                                      );
                                    },
                                    code: ({
                                      node,
                                      inline,
                                      className,
                                      children,
                                      ...props
                                    }) => {
                                      let content = children as string;
                                      if (
                                        Array.isArray(children) &&
                                        children.length === 1 &&
                                        typeof children[0] === "string"
                                      ) {
                                        content = children[0] as string;
                                      }
                                      if (typeof content === "string") {
                                        if (content.length) {
                                          if (content[0] === "▍") {
                                            return (
                                              <span className="form-modal-markdown-span"></span>
                                            );
                                          }
                                        }

                                        const match = /language-(\w+)/.exec(
                                          className || "",
                                        );

                                        return !inline ? (
                                          <CodeTabsComponent
                                            language={(match && match[1]) || ""}
                                            code={String(content).replace(
                                              /\n$/,
                                              "",
                                            )}
                                          />
                                        ) : (
                                          <code
                                            className={className}
                                            {...props}
                                          >
                                            {content}
                                          </code>
                                        );
                                      }
                                    },
                                  }}
                                >
                                  {content.reason}
                                </Markdown>
                              </span>
                            )}
                            {content.solution && (
                              <div className="mt-4">
                                <h3 className="pb-3 font-semibold">
                                  Steps to fix:
                                </h3>
                                <ol className="list-decimal pl-5">
                                  <li>Check the component settings</li>
                                  <li>Ensure all required fields are filled</li>
                                  <li>Re-run your flow</li>
                                </ol>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    }
                    return null;
                  })}
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  );
};
