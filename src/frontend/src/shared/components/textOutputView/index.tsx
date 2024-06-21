import { Textarea } from "../../../components/ui/textarea";

const TextOutputView = ({ left, value,onChange }) => {
  if (typeof value === "object" && Object.keys(value).includes("text")) {
    value = value.text;
  }
  return (
    <Textarea
      className={`w-full custom-scroll ${left ? "min-h-32" : "h-full"}`}
      placeholder={"Empty"}
      // update to real value on flowPool
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
};

export default TextOutputView;
