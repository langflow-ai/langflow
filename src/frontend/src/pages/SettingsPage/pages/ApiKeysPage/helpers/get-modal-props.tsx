export const getModalPropsApiKey = () => {
  const modalProps = {
    title: "Create API Key",
    description: "Create a secret API Key to use Langflow API.",
    inputPlaceholder: "My API Key",
    buttonText: "Generate API Key",
    generatedKeyMessage: (
      <>
        {" "}
        Please save this secret key somewhere safe and accessible. For security
        reasons, <strong>you won't be able to view it again</strong> through
        your account. If you lose this secret key, you'll need to generate a new
        one.
      </>
    ),
    showIcon: true,
    inputLabel: (
      <>
        <span className="text-sm">Description</span>{" "}
        <span className="text-muted-foreground text-xs">(optional)</span>
      </>
    ),
  };

  return modalProps;
};
