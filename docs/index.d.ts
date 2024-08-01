declare module "*.module.scss" {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module "@theme/*";

declare module "@components/*";

declare module "@docusaurus/*";
