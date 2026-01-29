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

## Docusaurus Versioning

The versioning configuration is found in `docusaurus.config.js`.

The version key `'current'` is a special Docusaurus keyword that refers to the work-in-progress docs. You can't change this key, but you can customize the `label`.

Versioning example for release version 1.8.x:

1. Before release, the `current` version contains work-in-progress docs that are ahead of version `1.7.x`. The `current` label should already be set to `1.8.x` (updated when you began working on the 1.8.x docset).
2. When ready to release 1.8.x, create a branch and run `yarn docusaurus docs:version 1.8.0` to snapshot the current docs. Use the full version number like `1.8.0` for the command, even though the label displays `1.8.x`.
3. After creating a new version, update `docusaurus.config.js`:

```javascript
docs: {
  lastVersion: '1.8.0', // Make 1.8.0 the latest version (use full version number)
  versions: {
    current: {
      label: '1.9.x', // Work-in-progress version (will become next release)
      path: 'next',
    },
    '1.8.0': {
      label: '1.8.x', // Label shows .x notation
      path: '1.8.0',
    },
    '1.7.0': {
      label: '1.7.x', // Label shows .x notation
      path: '1.7.0',
    },
  },
  onlyIncludeVersions: ['current', '1.8.0', '1.7.0'], // Include all versions
},
```

4. Test the deployment locally:

```bash
yarn build
yarn serve
```

5. Create a pull request to main, and merge to create your new release.
6. To create version 1.9.x, repeat the process: update the `current` label to `1.9.x` when you begin working on it, then when ready to release, run `yarn docusaurus docs:version 1.9.0`, update `docusaurus.config.js` with labels using `.x` notation, and merge to main.

- `current` = always the work-in-progress docs from `main` branch (ahead of all releases)
  - The version key must be `'current'` (Docusaurus keyword), but you can customize the displayed `label`
- `lastVersion` = the most recent released version (shown as "latest" in the UI).

See the [Docusaurus docs](https://docusaurus.io/docs/versioning) for more info.

### Disable versioning

1. Remove the versions configuration from `docusaurus.config.js`.
2. Delete the `docs/versioned_docs/` and `docs/versioned_sidebars/` directories.
3. Delete `docs/versions.json`.

### References

- [Official Docusaurus Versioning Documentation](https://docusaurus.io/docs/versioning)
- [Docusaurus Versioning Best Practices](https://docusaurus.io/docs/versioning#versioning-best-practices)
