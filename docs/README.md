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

## Docusaurus Versioning

The versioning configuration is found in `docusaurus.config.js`.

Versioning example for release version `1.9.x` on top of `1.8.x`:

1. Before release, the docs in the active release branch should already be set to `1.8.x`, the current version.
2. When ready to release `1.9.x`, create a branch and run `npm run docs:version -- 1.9.0` to snapshot the current docs.
3. After creating a new version, update `docusaurus.config.js` to include the 1.9.0 release:

```javascript
docs: {
  lastVersion: '1.9.0',
  versions: {
    '1.9.0': {
      label: '1.9.x',
      path: '1.9.0',
    },
    '1.8.0': {
      label: '1.8.x',
      path: '1.8.0',
    },
  },
},
```

4. Test the deployment locally:

```bash
npm run build
npm run serve
```

5. Create a pull request to main, and merge to create your new release.
6. To create version 2.0.x, repeat the process: update the active release branch docs to `2.0.x` when you begin working on it, then when ready to release, run `npm run docs:version -- 2.0.0`, update `docusaurus.config.js` with labels using `.x` notation, and merge to main.

- `lastVersion` = the most recent released version (shown as "latest" in the UI).

See the [Docusaurus docs](https://docusaurus.io/docs/versioning) for more info.

### Disable versioning

1. Remove the versions configuration from `docusaurus.config.js`.
2. Delete the `docs/versioned_docs/` and `docs/versioned_sidebars/` directories.
3. Delete `docs/versions.json`.

### References

- [Official Docusaurus Versioning Documentation](https://docusaurus.io/docs/versioning)
- [Docusaurus Versioning Best Practices](https://docusaurus.io/docs/versioning#versioning-best-practices)

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
