// Type declarations for CSS imports in Storybook
declare module "*.css" {
  const content: Record<string, never>;
  export default content;
}
