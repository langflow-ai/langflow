import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SidebarTrigger } from "@/components/ui/sidebar";
import ImportButtonComponent from "@/modals/fileManagerModal/components/importButtonComponent";

export const FilesPage = () => {
  return (
    <CardsWrapComponent
      onFileDrop={() => {}}
      dragMessage={`Drag your files here`}
    >
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
              {
                <>
                  {/* Search and filters */}
                  <div className="flex justify-between">
                    <div className="flex w-full xl:w-5/12">
                      <Input
                        icon="Search"
                        data-testid="search-store-input"
                        type="text"
                        placeholder={`Search files...`}
                        className="mr-2 w-full"
                        value={""}
                        onChange={() => {}}
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <ShadTooltip content="Upload File" side="bottom">
                        <Button
                          variant="outline"
                          className="!px-3 md:!px-4 md:!pl-3.5"
                          onClick={() => {}}
                          id="new-project-btn"
                          data-testid="new-project-btn"
                        >
                          <ForwardedIconComponent
                            name="Plus"
                            aria-hidden="true"
                            className="h-4 w-4"
                          />
                          <span className="hidden whitespace-nowrap font-semibold md:inline">
                            Upload
                          </span>
                        </Button>
                      </ShadTooltip>
                      <ImportButtonComponent>
                        <Button className="font-semibold">
                          Import from
                          <ForwardedIconComponent
                            name="ChevronDown"
                            className="ml-2 h-4 w-4"
                          />
                        </Button>
                      </ImportButtonComponent>
                    </div>
                  </div>
                </>
              }
            </div>
          </div>
        </div>
      </div>
    </CardsWrapComponent>
  );
};

export default FilesPage;
