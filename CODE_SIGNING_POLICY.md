# Code signing policy

**Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).**

This policy applies to release artifacts built from the public source repository at:

- Repository: https://github.com/AkashaForge/ama-gi-player
- Primary branch: `main`
- License: GNU General Public License v3.0
- Project website: https://github.com/AkashaForge/ama-gi-player

---

## Scope

Amagi-Player is released under the OSI-approved **GNU General Public License v3.0**
and is not commercially dual-licensed. Third-party components bundled with the
application (PyQt6, libtorrent, aiohttp, FFmpeg, etc.) remain under their
respective open-source licenses — see [`LICENSES.txt`](LICENSES.txt) for the
full list.

### Eligible artifacts for signing

Only the following artifacts are submitted for signing:

- The project-owned executable `amagi-player.exe`, built from `main.py` via
  Nuitka `--standalone`.
- The release archive `amagi-player-v*-windows.zip`, which contains the
  executable and its runtime dependencies.

### Non-eligible artifacts

Signing credentials must **not** be used for:

- Any file not built by this repository's CI workflow.
- Locally built binaries produced on a developer machine.
- Third-party executables or binaries shipped from other projects.
- Test artifacts, debug builds, or pre-release experimental packages.

---

## Trusted build and release process

Release artifacts submitted for signing must satisfy **all** of the following:

1. **Provenance** — originate from this repository and from the revision
   identified by a semantic version tag (e.g. `v2.0.10`). No unsigned,
   non-tagged builds may be submitted.
2. **Build environment** — be built by the workflow defined in
   `.github/workflows/release.yml` on **GitHub-hosted runners**
   (`windows-latest`). Self-hosted runners are not permitted for signing
   requests.
3. **Pinned dependencies** — install dependencies from the exact versions
   declared in `requirements.txt` (all versions pinned with `==`).
4. **Verification steps** — pass every verification step of the workflow,
   including:
   - import sanity check (PyQt6, libtorrent, aiohttp, etc.);
   - QtMultimedia plugin verification;
   - `whitelist_seed.db` sanity check;
   - `data/seed_posters/` presence and count check.
5. **Artifact upload** — the unsigned executable and ZIP must be uploaded as a
   GitHub Actions artifact **before** any SignPath signing request is made.
6. **Manual approval** — every signing request must receive explicit approval
   from an authorized approver in the SignPath web portal. Automated approval
   is not permitted.
7. **Post-signing integrity** — the signed artifact must be downloaded back,
   its hash verified, and only then published to GitHub Releases.

No private key material is ever stored in this repository or in GitHub Actions
secrets. SignPath holds the signing certificate on a hardware security module
(HSM), and the private key never leaves it.

---

## Team roles

This is a single-maintainer project.

| Role | GitHub handle | Responsibility |
|---|---|---|
| **Authors / Committers** | `@AkashaForge` | Write access to the repository; authority over the source code that is submitted for signing |
| **Reviewers** | `@AkashaForge` | Review all external Pull Requests before merge into `main` |
| **Approvers** | `@AkashaForge` | Manually approve **each** SignPath signing request in the SignPath portal |

### Multi-factor authentication (MFA)

All individuals assigned to a signing role (`Authors / Committers`,
`Reviewers`, `Approvers`) are required to use **multi-factor authentication**
on both their GitHub account and their SignPath account.

---

## Code review requirements

Every change to `main` is subject to the following review rules:

- External Pull Requests must be reviewed by the approver before merge.
- Changes affecting the release workflow (`.github/workflows/release.yml`),
  build configuration (`requirements.txt`, `pyproject.toml`), or the packaged
  data (`data/`, `ui/`) are considered **critical** and require explicit
  re-verification of the workflow before the next release.
- Force-pushes to `main` are permitted only by the approver and only after a
  local backup exists (e.g. a `backup-*` branch).

---

## Revocation

The maintainer will immediately request revocation of the certificate or of
individual signatures if any of the following occurs:

- A signed artifact is found to contain malware or unwanted software.
- A signed artifact is discovered to have been built from sources **other
  than** this repository.
- The signing credentials are suspected to have been compromised.
- The code signing policy is materially violated.

In the event of revocation, the affected release will be removed from GitHub
Releases, and a new signed release will be issued only after the root cause
has been identified and fixed.

---

## Contact

Questions about this policy, requests for clarification, or reports of
policy violations:

- **GitHub Issues** — https://github.com/AkashaForge/ama-gi-player/issues
- **Security-related contact** — see [`SECURITY.md`](SECURITY.md)

For security vulnerabilities in the release process itself, please use GitHub's
private vulnerability reporting feature and **do not** open a public issue.

---

## References

- [SignPath Foundation](https://signpath.org/)
- [SignPath.io — Documentation](https://docs.signpath.io/)
- [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0)
- [Project repository](https://github.com/AkashaForge/ama-gi-player)

---

<div align="right">

*Amagi-Player · Code Signing Policy · v1.0*

</div>