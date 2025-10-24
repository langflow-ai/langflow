import { memo, ReactNode } from "react";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { cn } from "@/utils/utils";
import {
  createSyntaxHighlighterStyle,
  operatingSystemTabs,
} from "../utils/mcpServerUtils";

// Types & Interfaces
interface MemoizedApiKeyButtonProps {
  apiKey: string;
  isGeneratingApiKey: boolean;
  generateApiKey: () => void;
}

interface MemoizedCodeTagProps {
  children: ReactNode;
  isCopied: boolean;
  copyToClipboard: () => void;
  isAuthApiKey: boolean | null;
  apiKey: string;
  isGeneratingApiKey: boolean;
  generateApiKey: () => void;
}

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

// Helper Components
const MemoizedApiKeyButton = memo(
  ({
    apiKey,
    isGeneratingApiKey,
    generateApiKey,
  }: MemoizedApiKeyButtonProps) => (
    <Button
      unstyled
      className="flex items-center gap-2 font-sans text-muted-foreground hover:text-foreground"
      disabled={apiKey !== ""}
      loading={isGeneratingApiKey}
      onClick={generateApiKey}
    >
      <ForwardedIconComponent
        name="Key"
        className="h-4 w-4"
        aria-hidden="true"
      />
      <span>{apiKey === "" ? "Generate API key" : "API key generated"}</span>
    </Button>
  ),
);
MemoizedApiKeyButton.displayName = "MemoizedApiKeyButton";

const MemoizedCodeTag = memo(
  ({
    children,
    isCopied,
    copyToClipboard,
    isAuthApiKey,
    apiKey,
    isGeneratingApiKey,
    generateApiKey,
  }: MemoizedCodeTagProps) => (
    <code className="relative block bg-background text-[13px]">
      <div className="absolute right-4 top-4 flex items-center gap-6">
        {isAuthApiKey && (
          <MemoizedApiKeyButton
            apiKey={apiKey}
            isGeneratingApiKey={isGeneratingApiKey}
            generateApiKey={generateApiKey}
          />
        )}
        <Button
          unstyled
          size="icon"
          className={cn("h-4 w-4 text-muted-foreground hover:text-foreground")}
          onClick={copyToClipboard}
        >
          <ForwardedIconComponent
            name={isCopied ? "Check" : "Copy"}
            className="h-4 w-4"
            aria-hidden="true"
            dataTestId={isCopied ? "icon-check" : "icon-copy"}
          />
        </Button>
      </div>
      <div className="overflow-x-auto p-4">
        <span>{children}</span>
      </div>
    </code>
  ),
);
MemoizedCodeTag.displayName = "MemoizedCodeTag";

// Main Component
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
