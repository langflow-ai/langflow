import { useEffect, useRef, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import getTabsOrder from "../../modals/apiModal/utils/get-tabs-order";
import { useDarkStore } from "../../stores/darkStore";
import useFlowStore from "../../stores/flowStore";
import { codeTabsPropsType } from "../../types/components";
import { cn } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { TweaksComponent } from "./components/tweaksComponent";

export default function CodeTabsComponent({
  open,
  flow,
  tabs,
  activeTab,
  setActiveTab,
  isMessage,
  tweaks,
  setActiveTweaks,
  activeTweaks,
  allowExport = false,
  isThereTweaks = false,
  isThereWH = false,
}: codeTabsPropsType) {
  const [isCopied, setIsCopied] = useState<Boolean>(false);
  const dark = useDarkStore((state) => state.dark);
  const unselectAll = useFlowStore((state) => state.unselectAll);

  useEffect(() => {
    if (tweaks && flow) {
      unselectAll();
    }
  }, []);

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

  const tabsOrder = getTabsOrder(isThereWH, isThereTweaks);

  const nodes = useRef(flow?.data?.nodes);

  useEffect(() => {
    nodes.current = flow?.data?.nodes;
  }, [flow?.data?.nodes]);

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
          {tweaks && (
            <div className={Number(activeTab) > 2 ? "hidden" : "flex gap-2"}>
              <Switch
                style={{
                  transform: `scaleX(${0.7}) scaleY(${0.7})`,
                }}
                id="tweaks-switch"
                onCheckedChange={setActiveTweaks}
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

          {Number(activeTab) < 5 && (
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
          {tabsOrder[idx].toLowerCase() !== "tweaks" ? (
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
          ) : tabsOrder[idx].toLowerCase() === "tweaks" && nodes.current ? (
            <>
              <TweaksComponent
                nodes={nodes.current}
                setNodes={(change) => {
                  let newChange =
                    typeof change === "function"
                      ? change(nodes.current)
                      : change;
                  nodes.current = newChange;
                  tweaks?.buildTweaks(newChange!);
                }}
                tweaks={tweaks?.tweaksList ?? []}
                open={open}
              />
            </>
          ) : null}
        </TabsContent>
      ))}
    </Tabs>
  );
}
