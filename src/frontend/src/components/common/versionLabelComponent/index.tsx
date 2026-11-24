interface VersionLabelProps {
  versionTag: string;
  description?: string | null;
  className?: string;
}

export default function VersionLabel({
  versionTag,
  description,
  className,
}: VersionLabelProps) {
  return (
    <span className={className}>
      {versionTag}
      {description && (
        <span className="font-normal text-muted-foreground">
          {" \u2014 "}
          {description}
        </span>
      )}
    </span>
  );
}
