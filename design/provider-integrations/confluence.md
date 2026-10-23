# Confluence Cloud preview

Status: draft
Owners (sign-off roles): platform owner, release owner

The lfx-confluence package owns provider confluence and the separate confluence_integrations category. Legacy lfx-bundles Confluence components retain their category and class identities.

| Capability | Auth and scope | Context | Delivery or API |
| --- | --- | --- | --- |
| Search pages by exact title or list one approved space | Delegated user and read:page:confluence | Hosted and self-managed | REST v2 pages with bounded explicit cursor |
| Read a current page and storage body | Delegated user and read:page:confluence | Hosted and self-managed | REST v2 page by ID |
| Create a current page in an approved space | Delegated user and read:page:confluence plus write:page:confluence | Hosted and self-managed | REST v2 page create with optional verified parent |
| Replace a page at the expected version | Delegated user and read:page:confluence plus write:page:confluence | Hosted and self-managed | REST v2 page update with optimistic content version |
| Observe newly created pages after a silent baseline | Delegated user, read:page:confluence and offline_access, background consent | Self-managed | Full bounded current-page snapshots |
| Observe higher versions of previously seen pages | Delegated user, read:page:confluence and offline_access, background consent | Self-managed | Full bounded current-page snapshots |

All capabilities are preview. One operator-configured Cloud site and approved numeric spaces constrain targets. The account and verified grant bind credentials to that site. New page creation uses createdAt rather than first appearance in the space. Snapshot observations cannot recover intermediate edits, deletion history or all changes during access gaps.

Data Center, Desktop, headless manual credentials, hosted triggers and push webhooks are unsupported. Setup, limits, rate handling, write ambiguity and recovery are documented in the [bundle README](../../src/bundles/confluence/README.md). Live tenant acceptance remains unverified.

## Sign-off

| Role | Name | Date | PR |
| --- | --- | --- | --- |
| platform owner | | | |
| release owner | | | |
