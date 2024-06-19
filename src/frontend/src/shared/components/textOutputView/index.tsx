import { Textarea } from "../../../components/ui/textarea";

const TextOutputView = ({ left, value }) => {
  if (typeof value === "object" && Object.keys(value).includes("text")) {
    value = value.text;
  }
  return (
    <Textarea
      className={`w-full custom-scroll ${left ? "min-h-32" : "h-full"}`}
      placeholder={"Empty"}
      // update to real value on flowPool
      value={value}
      readOnly
    />
  );
};

export default TextOutputView;
