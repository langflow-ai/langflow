# Website

This website is built using [Docusaurus 3](https://docusaurus.io/), a modern static website generator.

### Installation

```
$ yarn install
```

### Local Development

```
$ yarn start
```

This command starts a local development server and opens up a browser window. Most changes are reflected live without having to restart the server.

### Build

```
$ yarn build
```

This command generates static content into the `build` directory and can be served using any static contents hosting service, including `yarn serve`.

### Deployment

Using SSH:

```
$ USE_SSH=true yarn deploy
```

Not using SSH:

```
$ GIT_USER=<Your GitHub username> yarn deploy
```

If you are using GitHub pages for hosting, this command is a convenient way to build the website and push to the `gh-pages` branch.

## Docusaurus Versioning

The versioning configuration is found in `docusaurus.config.js`.

The version key `'current'` is a special Docusaurus keyword that refers to the work-in-progress docs. You can't change this key, but you can customize the `label`.

Versioning example for release version 1.7.0:

1. Before release, the `current` version contains work-in-progress docs that are ahead of version 1.7.0.
2. When ready to release 1.7.0, create a branch and run `yarn docusaurus docs:version 1.7.0` to snapshot the current docs.
3. After creating a new version, update `docusaurus.config.js`:

```javascript
docs: {
  lastVersion: '1.8.0', // Make 1.8.0 the latest version
  versions: {
    current: {
      label: 'Next', // Work-in-progress version (will become 1.9.0)
      path: 'next',
    },
    '1.8.0': {
      label: '1.8.0',
      path: '1.8.0',
    },
    '1.7.0': {
      label: '1.7.0',
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
6. To create version 1.8.0, repeat the process by creating a branch, running `yarn docusaurus docs:version 1.8.0`, updating `docusaurus.config.js`, and merging to main.

- `current` = always the work-in-progress docs from `main` branch (ahead of all releases)
  - The version key must be `'current'` (Docusaurus keyword), but you can customize the `label` shown to users..
- `lastVersion` = the most recent released version (shown as "latest" in the UI)

See the [Docusaurus docs](https://docusaurus.io/docs/versioning) for more info.

### Disable versioning

1. Remove the versions configuration from `docusaurus.config.js`.
2. Delete the `docs/versioned_docs/` and `docs/versioned_sidebars/` directories.
3. Delete `docs/versions.json`.

### References

- [Official Docusaurus Versioning Documentation](https://docusaurus.io/docs/versioning)
- [Docusaurus Versioning Best Practices](https://docusaurus.io/docs/versioning#versioning-best-practices)
