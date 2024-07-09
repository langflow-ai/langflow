/// <reference types="vite-plugin-svgr/client" />
import { useLocation, useNavigate } from "react-router-dom";
import BlogPost from "../../../../assets/undraw_blog_post_re_fy5x.svg?react";
import ChatBot from "../../../../assets/undraw_chat_bot_re_e2gj.svg?react";
import PromptChaining from "../../../../assets/undraw_cloud_docs_re_xjht.svg?react";
import APIRequest from "../../../../assets/undraw_real_time_analytics_re_yliv.svg?react";
import BasicPrompt from "../../../../assets/undraw_short_bio_re_fmx0.svg?react";
import TransferFiles from "../../../../assets/undraw_transfer_files_re_a2a9.svg?react";

import {
  Card,
  CardContent,
  CardDescription,
  CardTitle,
} from "../../../../components/ui/card";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import { UndrawCardComponentProps } from "../../../../types/components";
import { updateIds } from "../../../../utils/reactflowUtils";

export default function UndrawCardComponent({
  flow,
}: UndrawCardComponentProps): JSX.Element {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const navigate = useNavigate();
  const location = useLocation();
  const folderId = location?.state?.folderId;
  const setFolderUrl = useFolderStore((state) => state.setFolderUrl);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const folderIdUrl = folderId || myCollectionId || "";

  function selectImage() {
    switch (flow.name) {
      case "Blog Writer":
        return (
          <BlogPost
            style={{
              width: "65%",
              height: "65%",
            }}
            preserveAspectRatio="xMidYMid meet"
          />
        );
      case "Basic Prompting (Hello, World)":
        return (
          <BasicPrompt
            style={{
              width: "65%",
              height: "65%",
            }}
            preserveAspectRatio="xMidYMid meet"
          />
        );
      case "Memory Chatbot":
        return (
          <ChatBot
            style={{
              width: "70%",
              height: "70%",
            }}
            preserveAspectRatio="xMidYMid meet"
          />
        );
      case "API requests":
        return (
          <APIRequest
            style={{
              width: "70%",
              height: "70%",
            }}
            preserveAspectRatio="xMidYMid meet"
          />
        );
      case "Document QA":
        return (
          <TransferFiles
            style={{
              width: "80%",
              height: "80%",
            }}
            preserveAspectRatio="xMidYMid meet"
          />
        );
      case "Vector Store RAG":
        return (
          <PromptChaining
            style={{
              width: "80%",
              height: "80%",
            }}
            preserveAspectRatio="xMidYMid meet"
          />
        );
      default:
        return (
          <TransferFiles
            style={{
              width: "80%",
              height: "80%",
            }}
            preserveAspectRatio="xMidYMid meet"
          />
        );
    }
  }

  return (
    <Card
      onClick={() => {
        updateIds(flow.data!);
        addFlow(true, flow).then((id) => {
          setFolderUrl(folderId ?? "");
          navigate(`/flow/${id}/folder/${folderIdUrl}`);
        });
      }}
      className="h-64 w-80 cursor-pointer bg-background pt-4"
    >
      <CardContent className="h-full w-full">
        <div className="flex h-full w-full flex-col items-center justify-center rounded-md bg-muted p-1 align-middle">
          {selectImage()}
        </div>
      </CardContent>
      <CardDescription className="px-6 pb-4">
        <CardTitle className="text-lg text-primary">{flow.name}</CardTitle>
      </CardDescription>
    </Card>
  );
}
