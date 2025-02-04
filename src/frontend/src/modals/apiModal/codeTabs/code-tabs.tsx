import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useTweaksStore } from "@/stores/tweaksStore";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useDarkStore } from "../../../stores/darkStore";
import { codeTabsPropsType } from "../../../types/components";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TweaksComponent } from "@/components/core/codeTabsComponent/components/tweaksComponent";
import { AllNodeType } from "@/types/flow";
import { tabsArrayType } from "@/types/tabs";

type APITabsPropsType = {
    open?: boolean;
    tweaksNodes?: AllNodeType[];
    activeTweaks?: boolean;
    setActiveTweaks?: (value: boolean) => void;
};

export default function APITabsComponent({
    open,
    setActiveTweaks,
    activeTweaks,
}: APITabsPropsType) {
    const [isCopied, setIsCopied] = useState<Boolean>(false);
    const dark = useDarkStore((state) => state.dark);
    const nodes = useTweaksStore((state) => state.nodes);
    const tabsList: tabsArrayType = [
        {
            title: "Python",
            icon: "python",
            language: "python",
            code: "print('Hello, world!')",
            copyCode: "print('Hello, world!')",
        },
        {
            title: "JavaScript",
            icon: "javascript",
            language: "javascript",
            code: "console.log('Hello, world!');",
            copyCode: "console.log('Hello, world!');",
        },
        {
            title: "cURL",
            icon: "curl",
            language: "curl",
            code: "curl -X GET 'https://api.example.com/endpoint'",
            copyCode: "curl -X GET 'https://api.example.com/endpoint'",
        },
    ];
    const [activeTab, setActiveTab] = useState<number>(0);

    const copyToClipboard = () => {
        if (!navigator.clipboard || !navigator.clipboard.writeText) {
            return;
        }

        navigator.clipboard.writeText(tabsList[activeTab].code).then(() => {
            setIsCopied(true);

            setTimeout(() => {
                setIsCopied(false);
            }, 2000);
        });
    };

    return (
        <Tabs
            value={activeTab.toString()}
            className={
                "api-modal-tabs inset-0 m-0"
            }
            onValueChange={(value) => {
                setActiveTab(parseInt(value));
            }}
        >
            <div className="api-modal-tablist-div">
                {tabsList.length > 0 && tabsList[0].title !== "" ? (
                    <TabsList className="mt-[-1px] border-b">
                        {tabsList.map((tab, index) => (
                            <TabsTrigger
                                key={index}
                                value={index.toString()}
                            >
                                {tab.title}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                ) : (
                    <div></div>
                )}
            </div>

            {tabsList.map((tab, idx) => (
                <TabsContent
                    value={idx.toString()}
                    className="api-modal-tabs-content overflow-hidden dark"
                    key={idx} // Remember to add a unique key prop
                >
                    <div className="mt-2 flex h-full w-full flex-col">
                        <div className="flex w-full items-center justify-end gap-4 rounded-t-md border border-border bg-muted px-4 py-2">
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
                        </div>
                        <SyntaxHighlighter
                            language={tab.language}
                            style={oneDark}
                            className="!my-0 h-full overflow-auto rounded-sm !rounded-t-none border border-t-0 border-border text-left custom-scroll"
                        >
                            {tab.code}
                        </SyntaxHighlighter>
                    </div>
                </TabsContent>
            ))}
        </Tabs>
    );
}
