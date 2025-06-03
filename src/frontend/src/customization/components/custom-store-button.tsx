import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarMenuButton } from "@/components/ui/sidebar";

export const CustomStoreButton = () => {
  return (
    <>
      <div className="flex w-full items-center" data-testid="button-store">
        <SidebarMenuButton
          size="md"
          className="text-sm"
          onClick={() => {
            window.open("/store", "_blank");
          }}
        >
          <ForwardedIconComponent name="Store" className="h-4 w-4" />
          Store
        </SidebarMenuButton>
      </div>
    </>
  );
};
