import { Textarea } from "../../../components/ui/textarea";

const TextOutputView = ({
  left,
  value,
}: {
  left: boolean | undefined;
  value: any;
}) => {
  if (typeof value === "object" && Object.keys(value).includes("text")) {
    value = value.text;
  }
  return (
    <Textarea
      className={`w-full custom-scroll ${left ? "min-h-32" : "h-full"}`}
      placeholder={"Empty"}
      readOnly
      // update to real value on flowPool
      value={value}
    />
  );
};

export default TextOutputView;
