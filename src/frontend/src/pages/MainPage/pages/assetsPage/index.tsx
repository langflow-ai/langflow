import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import FilesTab from "./components/FilesTab";
import KnowledgeBasesTab from "./components/KnowledgeBasesTab";

export const FilesPage = () => {
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);
  const [quantitySelected, setQuantitySelected] = useState(0);
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [quickFilterText, setQuickFilterText] = useState("");
  const [tabValue, setTabValue] = useState("files");

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Shift") {
        setIsShiftPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Shift") {
        setIsShiftPressed(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  const tabProps = {
    quickFilterText,
    setQuickFilterText,
    selectedFiles,
    setSelectedFiles,
    quantitySelected,
    setQuantitySelected,
    isShiftPressed,
  };

  return (
    <div
      className="flex h-full w-full flex-col overflow-y-auto"
      data-testid="cards-wrapper"
    >
      <div className="flex h-full w-full flex-col xl:container">
        <div className="flex flex-1 flex-col justify-start px-5 pt-10">
          <div className="flex h-full flex-col justify-start">
            <div
              className="flex items-center pb-8 text-xl font-semibold"
              data-testid="mainpage_title"
            >
              <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
                <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
                  <SidebarTrigger>
                    <ForwardedIconComponent
                      name="PanelLeftOpen"
                      aria-hidden="true"
                      className=""
                    />
                  </SidebarTrigger>
                </div>
              </div>
              Assets
            </div>

            <Tabs
              defaultValue="files"
              className="flex h-full flex-col"
              onValueChange={setTabValue}
            >
              <TabsList className="mb-4 w-fit">
                <TabsTrigger value="files">Files</TabsTrigger>
                <TabsTrigger value="knowledge-bases">
                  Knowledge Bases
                </TabsTrigger>
              </TabsList>
              {tabValue === "files" && (
                <TabsContent value="files" className="flex h-full flex-col">
                  <FilesTab {...tabProps} />
                </TabsContent>
              )}
              {tabValue === "knowledge-bases" && (
                <TabsContent
                  value="knowledge-bases"
                  className="flex h-full flex-col"
                >
                  <KnowledgeBasesTab {...tabProps} />
                </TabsContent>
              )}
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FilesPage;
