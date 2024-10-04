import { useTweaksStore } from "@/stores/tweaksStore";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import { useDarkStore } from "../../stores/darkStore";
import { codeTabsPropsType } from "../../types/components";
import { cn } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { TweaksComponent } from "./components/tweaksComponent";

export default function CodeTabsComponent({
  open,
  tabs,
  activeTab,
  setActiveTab,
  isMessage,
  setActiveTweaks,
  activeTweaks,
}: codeTabsPropsType) {
  const [isCopied, setIsCopied] = useState<Boolean>(false);
  const dark = useDarkStore((state) => state.dark);
  const nodes = useTweaksStore((state) => state.nodes);

  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(tabs[activeTab].code).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };

  return (
    <Tabs
      value={activeTab}
      className={
        "api-modal-tabs inset-0 m-0 " +
        (isMessage ? "dark" : "") +
        (dark && isMessage ? "bg-background" : "")
      }
      onValueChange={(value) => {
        setActiveTab(value);
      }}
    >
      <div className="api-modal-tablist-div">
        {tabs.length > 0 && tabs[0].name !== "" ? (
          <TabsList>
            {tabs.map((tab, index) => (
              <TabsTrigger
                className={
                  isMessage ? "data-[state=active]:bg-primary-foreground" : ""
                }
                key={index}
                value={index.toString()}
              >
                {tab.name}
              </TabsTrigger>
            ))}
          </TabsList>
        ) : (
          <div></div>
        )}

        <div className="float-right mx-2 mb-1 mt-2 flex items-center gap-4">
          {nodes.length > 0 &&
            tabs.find((tab) => tab.name.toLowerCase() === "tweaks") &&
            tabs[activeTab].hasTweaks && (
              <div className="flex gap-2">
                <Switch
                  style={{
                    transform: `scaleX(${0.7}) scaleY(${0.7})`,
                  }}
                  id="tweaks-switch"
                  onCheckedChange={setActiveTweaks}
                  checked={activeTweaks}
                  autoFocus={false}
                />
                <Label
                  className={cn(
                    "relative right-1 top-[4px] text-xs font-medium text-muted-foreground",
                    activeTweaks ? "text-primary" : "",
                  )}
                  htmlFor="tweaks-switch"
                >
                  Tweaks
                </Label>
              </div>
            )}

          {tabs[activeTab].name.toLowerCase !== "tweaks" && (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground"
                onClick={copyToClipboard}
              >
                {isCopied ? (
                  <IconComponent name="Check" className="h-4 w-4" />
                ) : (
                  <IconComponent name="Copy" className="h-4 w-4" />
                )}
              </Button>
            </>
          )}
        </div>
      </div>

      {tabs.map((tab, idx) => (
        <TabsContent
          value={idx.toString()}
          className="api-modal-tabs-content overflow-hidden"
          key={idx} // Remember to add a unique key prop
        >
          {tab.name.toLowerCase() !== "tweaks" ? (
            <div className="flex h-full w-full flex-col">
              {tab.description && (
                <div
                  className="mb-2 w-full text-left text-sm"
                  dangerouslySetInnerHTML={{ __html: tab.description }}
                ></div>
              )}
              <SyntaxHighlighter
                language={tab.language}
                style={oneDark}
                className="mt-0 h-full overflow-auto rounded-sm text-left custom-scroll"
              >
                {tab.code}
              </SyntaxHighlighter>
            </div>
          ) : tab.name.toLowerCase() === "tweaks" ? (
            <>
              <TweaksComponent open={open} />
            </>
          ) : null}
        </TabsContent>
      ))}
    </Tabs>
  );
}
