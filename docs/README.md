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

Docs versioning is currently **DISABLED** but configured and ready to enable. The configuration is found in `docusaurus.config.js` with commented-out sections.

### To enable versioning:

1. Open `docusaurus.config.js`
2. Find the versioning configuration section (around line 104)
3. Uncomment the versioning configuration:

```javascript
docs: {
  // ... other config
  lastVersion: 'current', // Use 'current' to make ./docs the latest version
  versions: {
    current: {
      label: 'Next', // What users see
      path: 'next',  // URL path for this version
    },
  },
  onlyIncludeVersions: ['current'], // Limit versions for faster builds
},
```

The version key `'current'` is a special Docusaurus keyword that refers to the work-in-progress docs. You can't change this key, but you can customize the `label`.

### Typical Release Workflow

Here's how versioning works in practice:

**Example: Releasing version 1.7.0**

1. **Before release**: `current` contains work-in-progress docs (ahead of 1.7.0)
2. **When ready to release 1.7.0**: Run `yarn docusaurus docs:version 1.7.0` to snapshot current docs
3. **After 1.7.0 release**: Update config with `lastVersion: '1.7.0'` - this makes 1.7.0 the "latest" released version
4. **`current` continues**: The `current` version remains as work-in-progress (will become 1.8.0)
5. **When 1.8.0 launches**: Run `yarn docusaurus docs:version 1.8.0` to snapshot current docs

**Key points:**
- `current` = always the work-in-progress docs from `main` branch (ahead of all releases)
  - The version key must be `'current'` (Docusaurus keyword), but you can customize the `label` shown to users..
- `lastVersion` = the most recent released version (shown as "latest" in the UI)
- Each release snapshots `current` at that point in time

### Create docs versions

See the [Docusaurus docs](https://docusaurus.io/docs/versioning) for more info.

1. Use the Docusaurus CLI command to create a version.

```bash
# Create version 1.7.0 from current docs
yarn docusaurus docs:version 1.7.0
```

This command will:
- Copy the full `docs/` folder contents into `versioned_docs/version-1.7.0/`
- Create a versioned sidebar file at `versioned_sidebars/version-1.7.0-sidebars.json`
- Append the new version to `versions.json`

2. After creating a version, update the Docusaurus configuration to include multiple versions. `lastVersion: '1.7.0'` makes the '1.7.0' release the latest version. `current` is the work-in-progress docset, accessible at `/docs/next`. To remove a version, remove it from `onlyIncludeVersions`.

```javascript
docs: {
  // ... other config
  lastVersion: '1.7.0',
  versions: {
    current: {
      label: 'Next', // Work-in-progress version (will become 1.8.0)
      path: 'next',
    },
    '1.7.0': {
      label: '1.7.0',
      path: '1.7.0',
    },
  },
  onlyIncludeVersions: ['current', '1.7.0'],
},
```

3. Test the deployment locally:

```bash
yarn build
yarn serve
```

4. To add subsequent versions, repeat the process, first running the CLI command then updating `docusaurus.config.js`:

```bash
# Create version 1.8.0 from current docs
yarn docusaurus docs:version 1.8.0
```

After creating a new version, update `docusaurus.config.js`:

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

### Disable versioning

1. Remove the versions configuration from `docusaurus.config.js`
2. Delete the `docs/versioned_docs/` and `docs/versioned_sidebars/` directories
3. Delete `docs/versions.json`

### References

- [Official Docusaurus Versioning Documentation](https://docusaurus.io/docs/versioning)
- [Docusaurus Versioning Best Practices](https://docusaurus.io/docs/versioning#versioning-best-practices)
