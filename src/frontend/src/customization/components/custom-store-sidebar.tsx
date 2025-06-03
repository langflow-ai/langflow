import { ForwardedIconComponent } from "@/components/common/genericIconComponent";

export const CustomStoreSidebar = () => {
  return [
    {
      title: "Langflow API Keys",
      href: "/settings/api-keys",
      icon: (
        <ForwardedIconComponent
          name="Key"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: "Langflow Store",
      href: "/settings/store",
      icon: (
        <ForwardedIconComponent
          name="Store"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
  ];
};
