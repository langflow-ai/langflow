import { memo, useEffect, useState } from "react";
import useFlowStore from "@/stores/flowStore";
import type { errorMessagePropsType } from "../../../../../../types/components";
import { ErrorView } from "./components/content-view";

export const ErrorMessage = memo(
  ({ chat, lastMessage }: errorMessagePropsType) => {
    const fitViewNode = useFlowStore((state) => state.fitViewNode);
    const [showError, setShowError] = useState(false);
    useEffect(() => {
      if (chat.category === "error") {
        // Short delay before showing error to allow for loading animation
        const timer = setTimeout(() => {
          setShowError(true);
        }, 50);
        return () => clearTimeout(timer);
      }
    }, [chat.category]);

    const blocks = chat.content_blocks ?? [];

    return (
      <ErrorView
        blocks={blocks}
        showError={showError}
        lastMessage={lastMessage}
        fitViewNode={fitViewNode}
        chat={chat}
      />
    );
  },
);
