const NoResultsMessage = ({
  onClearSearch,
  message = "No components found.",
  clearSearchText = "Clear your search",
  additionalText = "or filter and try a different query.",
}) => {
  return (
    <div className="flex h-full flex-col items-center justify-center p-3 text-center">
      <p className="text-secondary-foreground text-sm">
        {message}{" "}
        <a
          className="cursor-pointer underline underline-offset-4"
          onClick={onClearSearch}
        >
          {clearSearchText}
        </a>{" "}
        {additionalText}
      </p>
    </div>
  );
};

export default NoResultsMessage;
