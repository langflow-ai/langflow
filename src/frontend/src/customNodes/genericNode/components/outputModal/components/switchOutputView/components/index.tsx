import { Textarea } from "../../../../../../../components/ui/textarea";

export default function ErrorOutput({ value }: { value: string }) {
  console.log(value);
  return (
    <Textarea
      className={`h-full w-full text-destructive custom-scroll`}
      placeholder={"Empty"}
      value={value}
      readOnly
    />
  );
}
