export default function DateReader({ date }: { date: string }): JSX.Element {
  const dateT = new Date(date);
  const formattedDate = dateT.toLocaleString("en-US", {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
  });
  return <span>{formattedDate}</span>;
}
