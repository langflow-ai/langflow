export default function DateReader({
  date: dateString,
}: {
  date: string;
}): JSX.Element {
  const date = new Date(dateString);

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0"); // Months are 0-indexed in JavaScript
  const day = String(date.getDate()).padStart(2, "0");

  const hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");

  const ampm = hours >= 12 ? "PM" : "AM";
  const hours12 = hours > 12 ? hours - 12 : hours === 0 ? 12 : hours; // Convert to 12-hour format

  const formattedDate = `${year}-${month}-${day} ${hours12}:${minutes} ${ampm}`;

  return <span>{formattedDate}</span>;
}
