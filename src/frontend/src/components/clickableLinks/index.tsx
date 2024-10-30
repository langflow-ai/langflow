interface ClickableLinksProps {
  text: string;
}

export default function ClickableLinks({
  text,
}: ClickableLinksProps): JSX.Element {
  // Regex to match URLs
  const urlRegex = /(https?:\/\/[^\s]+)/g;

  // Split text by URLs and map each part
  const parts = text.split(urlRegex);
  const matches = Array.from(text.matchAll(urlRegex), (m) => m[0]);

  return (
    <span>
      {parts.map((part, i) => {
        // If this part matches a URL, make it a link
        if (matches.includes(part)) {
          return (
            <a
              key={i}
              href={part}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              {part}
            </a>
          );
        }
        // Otherwise, return the text as is
        return part;
      })}
    </span>
  );
}
