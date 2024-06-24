export default function TextOutputComponent({
  text,
  emissor,
}: {
  text: string;
  emissor: string;
}) {
  return (
    <div>
      <strong>{emissor}</strong>
      <br></br>
      <div className="w-80 break-all">{text}</div>
    </div>
  );
}
