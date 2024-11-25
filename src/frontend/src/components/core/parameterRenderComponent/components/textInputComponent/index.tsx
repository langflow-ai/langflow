export default function TextInputComponent({
  text,
  emissor,
}: {
  text: string;
  emissor: string;
}) {
  return (
    <div>
      <strong> {emissor}</strong>
      <br></br>
      <span>{text}</span>
    </div>
  );
}
