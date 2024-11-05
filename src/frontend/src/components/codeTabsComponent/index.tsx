import ShadTooltip from "@/components/shadTooltipComponent";
import { useTweaksStore } from "@/stores/tweaksStore";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  oneDark,
  tomorrow,
} from "react-syntax-highlighter/dist/cjs/styles/prism";
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
          <TabsList className="mt-[-1px] border-b">
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
          className="api-modal-tabs-content overflow-hidden dark"
          key={idx} // Remember to add a unique key prop
        >
          {tab.name.toLowerCase() !== "tweaks" ? (
            <div className="mt-2 flex h-full w-full flex-col">
              {tab.description && (
                <div
                  className="mb-2 w-full text-left text-sm"
                  dangerouslySetInnerHTML={{ __html: tab.description }}
                ></div>
              )}
              <div className="flex w-full items-center justify-end gap-4 rounded-t-md border border-b-0 border-input bg-secondary px-4 py-2">
                {nodes.length > 0 &&
                  tabs.find((tab) => tab.name.toLowerCase() === "tweaks") &&
                  tabs[activeTab].hasTweaks && (
                    <div className="flex items-center gap-2">
                      <ShadTooltip content="Makes temporary adjustments managed in 'Tweaks'">
                        <div className="flex items-center gap-2">
                          <Label
                            className={"text-xs font-medium text-white"}
                            htmlFor="tweaks-switch"
                          >
                            Enable Tweaks
                          </Label>
                          <IconComponent
                            name="info"
                            className="h-3.5 w-3.5 text-placeholder-foreground"
                          />
                        </div>
                      </ShadTooltip>
                      <Switch
                        style={{
                          transform: `scaleX(${0.85}) scaleY(${0.85})`,
                        }}
                        id="tweaks-switch"
                        onCheckedChange={setActiveTweaks}
                        checked={activeTweaks}
                        autoFocus={false}
                      />
                      <span className="text-lg text-accent">|</span>
                    </div>
                  )}

                {tabs[activeTab].name.toLowerCase !== "tweaks" && (
                  <>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={copyToClipboard}
                      data-testid="btn-copy-code"
                    >
                      {isCopied ? (
                        <IconComponent
                          name="Check"
                          className="h-4 w-4 text-muted-foreground"
                        />
                      ) : (
                        <IconComponent
                          name="Copy"
                          className="h-4 w-4 text-muted-foreground"
                        />
                      )}
                    </Button>
                  </>
                )}
              </div>
              <SyntaxHighlighter
                language={tab.language}
                style={oneDark}
                className="!my-0 h-full overflow-auto rounded-sm !rounded-t-none border border-t-0 border-input bg-code-block text-left custom-scroll"
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
