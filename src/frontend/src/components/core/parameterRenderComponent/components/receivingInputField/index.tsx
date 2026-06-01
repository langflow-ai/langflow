import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";

/** Read-only "Receiving input" field shown when an input handle is connected. */
export function ReceivingInputField({
  id,
  editNode = false,
}: {
  id?: string;
  editNode?: boolean;
}): JSX.Element {
  return (
    <div className="relative flex w-full items-center">
      <input
        data-testid={id}
        id={id}
        readOnly
        disabled
        value=""
        placeholder={getPlaceholder(true)}
        className={cn("primary-input pr-9", editNode ? "h-6" : "h-9")}
      />
      <IconComponent
        name="lock"
        className="pointer-events-none absolute right-3 h-4 w-4 text-muted-foreground"
      />
    </div>
  );
}

export default ReceivingInputField;
