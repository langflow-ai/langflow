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
        <span className="text-xs text-muted-foreground">(optional)</span>
      </>
    ),
  };

  return modalProps;
};

// @TODO add this to DSLF repository
// import { Link } from "react-router-dom";

// export const DOCS_ACCESS_DATASTAX =
//   "https://docs.datastax.com/en/astra-db-classic/administration/manage-database-access.html#default-roles";

// export const getModalPropsApiKey = () => {
//   const orgId =
//     window.location.pathname.split("langflow/")[1]?.split("/")[0] || "";

//   const URL_DATASTAX_TOKENS_URL = `https://astra.datastax.com/org/${orgId}/settings/tokens`;

//   const modalProps = {
//     title: "Create new token",
//     description: (
//       <>
//         Generate a token with{" "}
//         <Link to={DOCS_ACCESS_DATASTAX} className="text-accent-pink-foreground">
//           Org Adm
//         </Link>{" "}
//         permissions. For custom roles, visit{" "}
//         <Link
//           to={URL_DATASTAX_TOKENS_URL}
//           className="text-accent-pink-foreground"
//         >
//           Tokens
//         </Link>
//         .
//       </>
//     ),
//     inputLabel: (
//       <>
//         <span className="text-sm">Description</span>{" "}
//         <span className="text-xs text-muted-foreground">(optional)</span>
//       </>
//     ),
//     inputPlaceholder: "New webhook key",
//     buttonText: "Create token",
//     generatedKeyMessage: (
//       <>
//         {" "}
//         Please save this secret key somewhere safe and accessible. For security
//         reasons, <strong>you won't be able to view it again</strong> through
//         your account. If you lose this secret key, you'll need to generate a new
//         one.
//       </>
//     ),
//     showIcon: false,
//   };

//   return modalProps;
// };
