// Fork builds are tagged `<upstream version>-thinkscape.<N>` (e.g.
// `5.4.0-thinkscape.4`) and published from the Thinkscape/romm fork. They have
// no GitHub releases there, only git tags, so their links point at the tag tree
// and the fork's commit history instead of upstream release pages.
export const UPSTREAM_REPO = "rommapp/romm";
export const FORK_REPO = "Thinkscape/romm";
export const FORK_BRANCH = "device-sync";

const FORK_VERSION_RE = /^(.+)-thinkscape\.\d+$/;

/** The upstream version a fork build is based on; null for non-fork versions. */
export function forkBaseVersion(version: string): string | null {
  return FORK_VERSION_RE.exec(version)?.[1] ?? null;
}

export function isForkVersion(version: string): boolean {
  return forkBaseVersion(version) !== null;
}

/** The version to compare against upstream releases (fork suffix stripped). */
export function upstreamVersion(version: string): string {
  return forkBaseVersion(version) ?? version;
}

/** The GitHub repository page the given version was built from. */
export function sourceRepoUrl(version: string): string {
  return `https://github.com/${isForkVersion(version) ? FORK_REPO : UPSTREAM_REPO}`;
}

/** Where a tagged version links: the fork's tag tree, or the upstream release. */
export function versionTagUrl(version: string): string {
  return isForkVersion(version)
    ? `https://github.com/${FORK_REPO}/tree/${version}`
    : `https://github.com/${UPSTREAM_REPO}/releases/tag/${version}`;
}

/** Upstream release page for a tag reported by the upstream releases API. */
export function upstreamReleaseUrl(tag: string): string {
  return `https://github.com/${UPSTREAM_REPO}/releases/tag/${tag}`;
}

export const FORK_COMMITS_URL = `https://github.com/${FORK_REPO}/commits/${FORK_BRANCH}`;

/**
 * GitHub compare API listing the fork's own commits between its upstream base
 * tag and the given fork version; null for non-fork versions.
 */
export function forkCompareApiUrl(version: string): string | null {
  const base = forkBaseVersion(version);
  if (base === null) return null;
  const [owner] = UPSTREAM_REPO.split("/");
  return `https://api.github.com/repos/${FORK_REPO}/compare/${owner}:${base}...${version}`;
}
