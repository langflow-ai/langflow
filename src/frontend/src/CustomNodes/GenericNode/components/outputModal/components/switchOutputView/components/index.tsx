import { Textarea } from "../../../../../../../components/ui/textarea";

export default function ErrorOutput({ value }: { value: string }) {
  return (
    <Textarea
      className={`text-destructive custom-scroll h-full w-full`}
      placeholder={"Empty"}
      value={value}
      readOnly
    />
  );
}
