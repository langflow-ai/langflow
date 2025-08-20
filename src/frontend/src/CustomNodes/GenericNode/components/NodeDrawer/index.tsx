import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader
} from "@/components/ui/sidebar";

type NodeDrawerProps = {
  open: boolean;
  onClose: () => void;
  nodeId: string;
}

const NodeDrawer = ({ open, onClose, nodeId }: NodeDrawerProps) => {
  return (
    <Sidebar variant="sidebar" collapsible="none" side="right">
      <SidebarHeader className="px-4 py-2">
        {/* Header content goes here */}
      </SidebarHeader>
      
      <SidebarContent className="px-4 py-2">
        {/* Main content goes here */}
      </SidebarContent>
      
      <SidebarFooter className="px-4 py-2">
        {/* Footer content goes here */}
      </SidebarFooter>
    </Sidebar>
  );
};

export default NodeDrawer;