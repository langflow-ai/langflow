export interface CustomAdminPageMenuItemProps {
  onNavigate: (path: string) => void;
}

// OSS has no admin page. Enterprise overlays this seam with the /admin-ee entry.
export const CustomAdminPageMenuItem = (_: CustomAdminPageMenuItemProps) =>
  null;

export default CustomAdminPageMenuItem;
