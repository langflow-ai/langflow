# Website

This website is built using [Docusaurus 3](https://docusaurus.io/), a modern static website generator.

### Installation

```
$ npm install
```

### Local Development

```
$ npm run start
```

This command starts a local development server and opens up a browser window. Most changes are reflected live without having to restart the server.

### Build

```
$ npm run build
```

This command generates static content into the `build` directory and can be served using any static contents hosting service, including `npm run serve`.

### Import code snippets from the repo with a line range

To pull a slice of a file into the docs, source the content with `raw-loader` and present the code with the `CodeSnippet` component.
For a working example, see the [Components overview](/concepts-components#component-code).

```mdx
import CodeSnippet from "@site/src/components/CodeSnippet";
import customComponent from "!!raw-loader!@langflow/src/lfx/src/lfx/custom/custom_component/custom_component.py";

<CodeSnippet
  source={customComponent}
  startLine={41}
  endLine={74}
  language="python"
  title="CustomComponent metadata (from codebase)"
  showLineNumbers
/>
```

### Deployment

Using SSH:

```
$ USE_SSH=true npm run deploy
```

Not using SSH:

```
$ GIT_USER=<Your GitHub username> npm run deploy
```

If you are using GitHub pages for hosting, this command is a convenient way to build the website and push to the `gh-pages` branch.
