import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";

interface HeaderTitleProps {
  folderName: string;
}

const HeaderTitle = ({ folderName }: HeaderTitleProps) => (
  <div
    className="flex items-center pb-4 text-xl font-semibold"
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
    {folderName}
  </div>
);

export default HeaderTitle;
