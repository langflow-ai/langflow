import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";
import FilesTab from "./components/FilesTab";

export const FilesPage = () => {
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);
  const [quantitySelected, setQuantitySelected] = useState(0);
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [quickFilterText, setQuickFilterText] = useState("");

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
              Files
            </div>
            <div className="flex h-full flex-col">
              <FilesTab {...tabProps} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FilesPage;
