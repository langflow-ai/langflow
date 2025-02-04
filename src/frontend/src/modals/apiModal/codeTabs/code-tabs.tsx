import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useTweaksStore } from "@/stores/tweaksStore";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/cjs/styles/prism";
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
            icon: "BWPython",
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
            icon: "TerminalSquare",
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
            <div className="flex items-center justify-between">
                {tabsList.length > 0 && tabsList[0].title !== "" ? (
                    <TabsList className="flex items-center bg-muted w-fit rounded p-1">
                        {tabsList.map((tab, index) => (
                            <TabsTrigger
                                key={index}
                                value={index.toString()}
                                className="flex items-center px-4 py-2 rounded-md !border-0 data-[state=active]:bg-background !text-[14px] gap-2.5"
                            >
                                <IconComponent name={tab.icon} className="h-4 w-4" />
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
                    <div className=" flex h-full w-full relative">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={copyToClipboard}
                            data-testid="btn-copy-code"
                            className="absolute top-2 right-2 group !hover:bg-foreground bg-muted-foreground"
                        >
                            {isCopied ? (
                                <IconComponent
                                    name="Check"
                                    className="h-5 w-5 text-muted group-hover:text-muted-foreground"
                                />
                            ) : (
                                <IconComponent
                                    name="Copy"
                                    className="!h-5 !w-5 text-muted group-hover:text-muted-foreground"
                                />
                            )}
                        </Button>
                        <SyntaxHighlighter
                            showLineNumbers={true}
                            wrapLongLines={true}
                            language="html"
                            style={dark ? oneDark : oneLight}
                            className="!mt-0 h-full w-full overflow-scroll !rounded-b-md border border-border text-left !custom-scroll"
                        >
                            {tab.code}
                        </SyntaxHighlighter>
                    </div>
                </TabsContent>
            ))}
        </Tabs>
    );
}
