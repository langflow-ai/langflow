import { ReactNode } from "react";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import {
  createSyntaxHighlighterStyle,
  operatingSystemTabs,
} from "../utils/mcpServerUtils";
import { MemoizedCodeTag } from "./McpCodeDisplay";

interface McpJsonContentProps {
  selectedPlatform?: string;
  setSelectedPlatform: (platform: string) => void;
  isDarkMode: boolean;
  isCopied: boolean;
  copyToClipboard: (text: string) => void;
  mcpJson: string;
  isAuthApiKey: boolean | null;
  apiKey: string;
  isGeneratingApiKey: boolean;
  generateApiKey: () => void;
}

export const McpJsonContent = ({
  selectedPlatform,
  setSelectedPlatform,
  isDarkMode,
  isCopied,
  copyToClipboard,
  mcpJson,
  isAuthApiKey,
  apiKey,
  isGeneratingApiKey,
  generateApiKey,
}: McpJsonContentProps) => (
  <>
    <Tabs value={selectedPlatform} onValueChange={setSelectedPlatform}>
      <TabsList>
        {operatingSystemTabs.map((tab) => (
          <TabsTrigger
            className="flex items-center gap-2"
            key={tab.name}
            value={tab.name}
          >
            <ForwardedIconComponent name={tab.icon} aria-hidden="true" />
            {tab.title}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
    <div className="overflow-hidden rounded-lg border border-border">
      <SyntaxHighlighter
        style={createSyntaxHighlighterStyle(isDarkMode)}
        CodeTag={({ children }: { children: ReactNode }) => (
          <MemoizedCodeTag
            isCopied={isCopied}
            copyToClipboard={() => copyToClipboard(mcpJson)}
            isAuthApiKey={isAuthApiKey}
            apiKey={apiKey}
            isGeneratingApiKey={isGeneratingApiKey}
            generateApiKey={generateApiKey}
          >
            {children}
          </MemoizedCodeTag>
        )}
        language="json"
      >
        {mcpJson}
      </SyntaxHighlighter>
    </div>
    <div className="px-2 text-mmd text-muted-foreground">
      Add this config to your client of choice. Need help? See the{" "}
      <a
        href="https://docs.langflow.org/mcp-server#connect-clients-to-use-the-servers-actions"
        target="_blank"
        rel="noreferrer"
        className="text-accent-pink-foreground"
      >
        setup guide
      </a>
      .
    </div>
  </>
);
