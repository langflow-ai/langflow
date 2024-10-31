import { useTweaksStore } from "@/stores/tweaksStore";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { tomorrow } from "react-syntax-highlighter/dist/cjs/styles/prism";
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
          <TabsList className="border-b mt-[-1px]">
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
              <div className="w-full rounded-t-md mt-2 px-4 py-2 flex items-center justify-end gap-4 bg-canvas-dark ">
                {nodes.length > 0 &&
                  tabs.find((tab) => tab.name.toLowerCase() === "tweaks") &&
                  tabs[activeTab].hasTweaks && (
                    <div className="flex items-center gap-2">
                      <Label
                        className={"text-xs font-medium text-white"}
                        htmlFor="tweaks-switch"
                      >
                        Enable Tweaks
                      </Label>
                      <Switch
                        style={{
                          transform: `scaleX(${0.85}) scaleY(${0.85})`,
                        }}
                        id="tweaks-switch"
                        onCheckedChange={setActiveTweaks}
                        checked={activeTweaks}
                        autoFocus={false}
                      />
                      <span className="text-lg text-primary dark:text-primary-foreground">|</span>
                    </div>
                  )}

                {tabs[activeTab].name.toLowerCase !== "tweaks" && (
                  <>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-[#A1A1AA]"
                      onClick={copyToClipboard}
                      data-testid="btn-copy-code"
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
              <SyntaxHighlighter
                language={tab.language}
                style={tomorrow}
                className="!mt-0 !rounded-t-none h-full overflow-auto rounded-sm text-left custom-scroll bg-code-block"
              >
                {tab.code}
              </SyntaxHighlighter>
            </div>
          ) : tab.name.toLowerCase() === "tweaks" ? (
            <>
              <TweaksComponent open={open ?? false} />
            </>
          ) : null}
        </TabsContent>
      ))}
    </Tabs>
  );
}
