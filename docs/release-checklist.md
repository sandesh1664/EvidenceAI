# Milestone 12 release checklist

Decision vocabulary: **PASS**, **FAIL**, **NOT VERIFIED**. A missing result never
becomes a pass. See [formal acceptance](release-acceptance.md) and the
[machine-readable criteria](evidence/m12/release-result.json).

| Requirement | Result | Required next action / owner |
| --- | --- | --- |
| Exact starting revision and changed-source hashes | PASS | Preserve source manifest with review artifacts / release engineer. |
| Existing records, revision and development Compose preserved | PASS | Recheck private before/after hashes before further experiments / maintainer. |
| No high/critical runtime image findings | FAIL | Remediate final inventories; obtain new scans. No self-approved exceptions / security and infrastructure. |
| Python/runtime JavaScript dependency audits | PASS | Repeat against final promoted artifacts / security. |
| Development lint-chain dependency advisory | FAIL | Track compatible upstream fix; no framework downgrade / frontend maintainer. |
| Registration hides account existence | FAIL | Implement verified generic enrollment / identity and product maintainers. |
| Automated authentication, RBAC, storage, concurrency guards | PASS | Review fixture scope; independent penetration test remains unverified / security. |
| Deterministic AI citation/isolation guards | PASS | Keep failed abstention evidence / AI maintainer. |
| Hosted-model quality and adversarial acceptance | NOT VERIFIED | Run approved provider/dataset evaluation with semantic review / AI owner. |
| Bounded local performance thresholds | PASS | Rehearse representative documents, real provider, longer soak and intended host / SRE. |
| Local encrypted backup/restored application and queue | PASS | Escrow keys and rehearse independent offsite recovery / SRE. |
| Production RTO/RPO, offsite delivery and alert receipt | NOT VERIFIED | Measure end-to-end loss and duration on intended infrastructure / SRE. |
| Desktop/mobile Chromium, Firefox, WebKit flows | PASS | Test intended physical devices, assistive technology and browser policy / QA. |
| Local workflow lint, migration and runtime guards | PASS | Preserve logs and pinned tools / release engineer. |
| Exact-SHA passing CI required before SSH | PASS | Source guard and lint verified; remote execution still unverified / release engineer. |
| Hosted CI, branch/environment protection and remote SSH | NOT VERIFIED | Configure/check actual main protection, reviewers/no self-approval and pinned host key / repository administrator. |
| Whole-image independent reproducibility and AMD64 acceptance | NOT VERIFIED | Freeze OS/package artifacts and rebuild/test target architecture / release engineer. |
| Public ACME/renewal, DNS/firewall and delivery monitoring | NOT VERIFIED | Verify after separate authorization and infrastructure preparation / infrastructure owner. |
| Named owners accept residual risk; reviewed accepted release exists | NOT VERIFIED | Assign owners; remediate and review evidence. No exception granted here / release authority. |
| Production promotion | FAIL | **BLOCKED**. Do not deploy this candidate. |

No commit, push, public deployment, purchase, DNS change, development data reset
or volume deletion is part of this milestone. All unchecked production conditions
must remain visible when a later release is reviewed.
