export interface CustomAdminPageMenuItemProps {
  onNavigate: (path: string) => void;
}

export const SHOW_LEGACY_ADMIN_PAGE = true;

export const CustomAdminPageMenuItem = (_: CustomAdminPageMenuItemProps) =>
  null;

export default CustomAdminPageMenuItem;
