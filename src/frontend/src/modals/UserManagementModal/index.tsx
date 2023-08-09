import { useState } from "react";
import { Button } from "../../components/ui/button";
import { ConfirmationModalType, UserManagementType } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";
import BaseModal from "../baseModal";
import * as Form from '@radix-ui/react-form';

export default function UserManagementModal({
  title,
  titleHeader,
  cancelText,
  confirmationText,
  children,
  icon,
  data,
  index,
  onConfirm,
}: UserManagementType) {
  const Icon: any = nodeIconsLucide[icon];

  const [open, setOpen] = useState(false);
  return (
    <BaseModal size="medium" open={open} setOpen={setOpen}>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Header description={titleHeader}>
        <span className="pr-2">{title}</span>
        <Icon
          name="icon"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>


  <Form.Root className="FormRoot">
    <Form.Field className="FormField" name="email">
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <Form.Label className="FormLabel">Email</Form.Label>
        <Form.Message className="FormMessage" match="valueMissing">
          Please enter your email
        </Form.Message>
        <Form.Message className="FormMessage" match="typeMismatch">
          Please provide a valid email
        </Form.Message>
      </div>
      <Form.Control asChild>
        <input className="Input" type="email" required />
      </Form.Control>
    </Form.Field>
    <Form.Field className="FormField" name="question">
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <Form.Label className="FormLabel">Question</Form.Label>
        <Form.Message className="FormMessage" match="valueMissing">
          Please enter a question
        </Form.Message>
      </div>
      <Form.Control asChild>
        <textarea className="Textarea" required />
      </Form.Control>
    </Form.Field>
    <Form.Submit asChild>
      <button className="Button" style={{ marginTop: 10 }}>
        Post question
      </button>
    </Form.Submit>
  </Form.Root>


      </BaseModal.Content>

      <BaseModal.Footer>
        <Button
          className="ml-3"
          onClick={() => {
            setOpen(false);
            onConfirm(index, data);
          }}
        >
          {confirmationText}
        </Button>

        <Button
          variant="outline"
          onClick={() => {
            setOpen(false);
          }}
        >
          {cancelText}
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
