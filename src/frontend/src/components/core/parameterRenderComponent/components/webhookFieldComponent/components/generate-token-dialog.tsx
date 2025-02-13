import { Button } from "@/components/ui/button";
import BaseModal from "@/modals/baseModal";
import { ReactNode, useState } from "react";
export default function GenerateTokenDialog({
  children,
}: {
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <BaseModal
      size="smaller-h-full"
      open={open}
      setOpen={setOpen}
      onSubmit={() => {}}
    >
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header description="Generate a token for the webhook">
        <span className="pr-2">Generate token</span>
      </BaseModal.Header>
      <BaseModal.Content>
        <div>diasjdiosajoidsa</div>
      </BaseModal.Content>

      <BaseModal.Footer submit={{ label: "Export" }} />
    </BaseModal>
  );
}
