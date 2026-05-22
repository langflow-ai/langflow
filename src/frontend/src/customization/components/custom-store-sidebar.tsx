import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import i18n from "@/i18n";

export const CustomStoreSidebar = (
  hasApiKey: boolean = false,
  hasStore: boolean = false,
) => {
  const items: Array<{ title: string; href: string; icon: JSX.Element }> = [];

  if (hasApiKey) {
    items.push({
      title: i18n.t("settings.nav.apiKeys"),
      href: "/settings/api-keys",
      icon: (
        <ForwardedIconComponent
          name="Key"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  if (hasStore) {
    items.push({
      title: i18n.t("settings.nav.store"),
      href: "/settings/store",
      icon: (
        <ForwardedIconComponent
          name="Store"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  return items;
};
