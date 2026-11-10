// Shared by candidate preparation and the final-publication gate.
async function findRelease(github, repo, tag) {
  try {
    const { data } = await github.rest.repos.getReleaseByTag({ ...repo, tag });
    return data;
  } catch (error) {
    if (error.status !== 404) throw error;
  }
  // The tag endpoint describes published releases. A write-capable token can
  // also see drafts through the list endpoint, including a failed final publish.
  const releases = await github.paginate(github.rest.repos.listReleases, {
    ...repo,
    per_page: 100,
  });
  return releases.find((release) => release.tag_name === tag);
}

async function assertCandidateReplaceable(github, repo, tag) {
  const release = await findRelease(github, repo, tag);
  if (release && !release.prerelease) {
    throw new Error(`Final publication is reserved or complete for ${tag}; use a new version.`);
  }
}

async function reserveFinalPublication(github, repo, tag, sha) {
  if (!/^v\d+\.\d+\.\d+$/.test(tag) || !/^[0-9a-f]{40}$/i.test(sha)) {
    throw new Error('Final publication requires a version tag and its full commit SHA.');
  }
  const { data: commit } = await github.rest.repos.getCommit({ ...repo, ref: tag });
  if (commit.sha.toLowerCase() !== sha.toLowerCase()) {
    throw new Error(`${tag} no longer matches the release commit; start a new release run.`);
  }
  const release = await findRelease(github, repo, tag);
  if (release) {
    if (release.prerelease) {
      throw new Error(`Remove or convert the prerelease record for ${tag} before final publication.`);
    }
    return; // Retry the same final source without replacing an existing release.
  }
  // Reserve before the first external publish, not after all packages succeed.
  // Omit target_commitish: the tag already exists and Actions lacks workflow-write scope.
  await github.rest.repos.createRelease({
    ...repo,
    tag_name: tag,
    name: tag,
    draft: true,
    prerelease: false,
    body: `Final artifact publication reserved from ${sha}. Keep this record if publication fails; ` +
      'it prevents candidate replacement after a partial publish. Retry using the same commit.',
  });
}

module.exports = { assertCandidateReplaceable, reserveFinalPublication };
