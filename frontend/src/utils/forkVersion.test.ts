import { describe, expect, it } from "vitest";
import {
  FORK_COMMITS_URL,
  forkBaseVersion,
  forkCompareApiUrl,
  isForkVersion,
  sourceRepoUrl,
  upstreamReleaseUrl,
  upstreamVersion,
  versionTagUrl,
} from "./forkVersion";

describe("forkVersion", () => {
  it("recognises a fork build and its upstream base", () => {
    expect(isForkVersion("5.4.0-thinkscape.4")).toBe(true);
    expect(forkBaseVersion("5.4.0-thinkscape.4")).toBe("5.4.0");
    expect(upstreamVersion("5.4.0-thinkscape.12")).toBe("5.4.0");
  });

  it("keeps an upstream pre-release base intact", () => {
    expect(forkBaseVersion("5.5.0-beta.1-thinkscape.2")).toBe("5.5.0-beta.1");
  });

  it.each([
    "5.4.0",
    "development",
    "nightly-a1b2c3d",
    "5.4.0-thinkscape",
    "5.4.0-thinkscape.4-dirty",
  ])("treats %s as a non-fork version", (version) => {
    expect(isForkVersion(version)).toBe(false);
    expect(forkBaseVersion(version)).toBeNull();
    expect(upstreamVersion(version)).toBe(version);
    expect(forkCompareApiUrl(version)).toBeNull();
  });

  it("links a fork build to its tag tree in the fork (no GitHub releases there)", () => {
    expect(versionTagUrl("5.4.0-thinkscape.4")).toBe(
      "https://github.com/Thinkscape/romm/tree/5.4.0-thinkscape.4",
    );
    expect(sourceRepoUrl("5.4.0-thinkscape.4")).toBe(
      "https://github.com/Thinkscape/romm",
    );
  });

  it("links an upstream build to its upstream release", () => {
    expect(versionTagUrl("5.4.0")).toBe(
      "https://github.com/rommapp/romm/releases/tag/5.4.0",
    );
    expect(sourceRepoUrl("5.4.0")).toBe("https://github.com/rommapp/romm");
    expect(upstreamReleaseUrl("5.5.0")).toBe(
      "https://github.com/rommapp/romm/releases/tag/5.5.0",
    );
  });

  it("compares a fork build against its upstream base tag", () => {
    expect(forkCompareApiUrl("5.4.0-thinkscape.4")).toBe(
      "https://api.github.com/repos/Thinkscape/romm/compare/rommapp:5.4.0...5.4.0-thinkscape.4",
    );
    expect(FORK_COMMITS_URL).toBe(
      "https://github.com/Thinkscape/romm/commits/device-sync",
    );
  });
});
