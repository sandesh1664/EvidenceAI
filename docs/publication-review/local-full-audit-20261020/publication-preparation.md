# Prepared private publication branch

This branch starts at the last published commit and contains **no new commit yet**.
The pending index contains all intended staged audit code, unpublished preservation
code, 15 approved JSON receipts, three SAFE original reports, two SAFE anonymized
verification reports at their canonical paths, and reviewed publication metadata.

The unpublished main commit containing the NEEDS REVIEW original is not an ancestor.
No cherry-pick, merge, rebase, history rewrite or main/index reset was used. Original
reports, original index, staged patch and a main-history bundle remain in a separate
restricted local custody directory; that directory is not part of this branch.

The two canonical verification report paths contain bytes from the existing SAFE
`.sanitized.md` derivatives. Those derivatives are also included at their review-bundle
paths so existing publication-review links work. The historical review's original-source
hashes/classifications still describe the restricted originals. `publication-plan.json`
explicitly maps those sources to the safe published bytes; it does not assert that an
original source digest should match its anonymized substitute.

Original FAIL, BLOCKED and NOT VERIFIED findings and all approved JSON bytes are
retained. Publication safety is separate from production readiness: production remains
BLOCKED. No development database/storage access or hosted deployment was involved.

## Validation boundary

The exact repository secret gate scans all reachable refs, current source and historical
archives. It must run in this independent checkout: running it in the original repository
would additionally include local main/custody history, which intentionally retains the
unpublished original. No scanner rules, adjudications, severities or release controls
were relaxed. No finding was silently allowlisted.

The preparation receipt outside this checkout records the exact staged tree and source
index preservation, gate outputs and negative original-blob/commit reachability checks.
After creating a commit, the owner must re-run the gate and history inspection before
an explicit branch-only push. Before a new commit exists, only the already-published
base is reachable as branch history; intended new bytes are staged, not committed.

## Owner-only final steps (not executed during preparation)

Use the isolated publication checkout, not the original main working tree. Verify the
branch and remote, inspect `git diff --cached`, then make the reviewed commit. Re-run:

```sh
python3 infra/security/scan_secrets.py --private-directory "$PRIVATE_CASE/post-commit-secret-evidence"
git diff --check
git log --oneline --decorate
```

The private scan directory must be a new path outside the checkout. Verify the new
commit descends directly from the published base and neither restricted original blob
nor the excluded local commit is reachable. Push only the explicit publication branch
if authorized. Never use `--all`, `--mirror`, force options, or push local main/tags.

This is not a whole-history privacy clearance for content already published before
the base commit. It excludes only the two reviewed unpublished original reports and
preserves the approved published ancestry byte-for-byte.
