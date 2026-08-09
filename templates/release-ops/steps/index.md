# Steps

0. [Preflight](0-preflight.md): verify the repo is ready to release. Clean tree, auth, optional tests.
1. [Collect](1-collect.md): gather changes since the last release tag. Detect commit style.
2. [Changelog](2-changelog.md): draft a changelog entry from the collected changes.
3. [Bump](3-bump.md): propose and apply the version bump. Wait for approval.
4. [Publish](4-publish.md): tag, push, and publish to the registry. Skipped if no registry.
5. [Announce](5-announce.md): post release notes to notification sink. Skipped if not configured.
