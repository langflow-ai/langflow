import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type DialogComponentProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  children: React.ReactNode;
};

const DialogComponent = ({ open, onOpenChange }) => {
  const content = [
    {
      icon: "something",
      label: "actions",
      actions: 12,
    },
    {
      icon: "something",
      label: "actions",
      actions: 50,
    },
    {
      icon: "something",
      label: "actions",
      actions: 23,
    },
  ];

  const renderSearchInput = () => (
    <div className="flex items-center rounded-md border px-3">
      <Button unstyled>all</Button>
      <ForwardedIconComponent
        name="search"
        className="mr-2 h-4 w-4 shrink-0 opacity-50"
      />
      <input
        //   onChange={searchRoleByTerm}
        placeholder="Search options..."
        className="flex h-9 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
        autoComplete="off"
      />
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-2 px-1 py-6">
        <div>
          {renderSearchInput()}
          <div className="flex flex-col gap-5 overflow-y-auto px-5">
            {content.map((item) => (
              // Change Key
              <div key={item.label} className="flex items-center gap-2">
                <ForwardedIconComponent name={item.icon} />
                <div className="flex items-center gap-2">
                  <div className="text-foreground">{item.label}</div>
                  <div className="text-muted-foreground">
                    {item.actions} actions
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default DialogComponent;
