# Grafana remediation experiments — not release candidates

Neither recipe is referenced by production Compose, CI packaging or deployment.
The unchanged strict image gate rejects the selected upstream image. Do not
configure unsigned-plugin allowances, remove datasource binaries, or waive scans.

`Dockerfile` retries the 12.1 core experiment with checksum-pinned v13.2.4 source,
Go 1.27.2, kin-openapi 0.149.0 and reusable Go caches. The dependency patch retains
Go checksums. Building core cannot repair the thirteen separately distributed
plugins (56 of 61 occurrences). The image reports patched commit `0e79aef...`,
whereas the release tag is `af4a33e...`; a tag rebuild has not demonstrated parity
with that patched distribution. Successful compilation alone would not authorize
replacement. Require vendor source parity, upstream tests, complete image scans,
startup/provisioning/query tests and artifact review before selecting any rebuild.

`opentsdb.Dockerfile` overlays the full official, signed, checksum-pinned 13.0.5
plugin (ARM64/AMD64 packages) on the existing pinned image. The ARM64 candidate was
built and scanned in 12.2. Its binary still has the same four high findings; the
full image remains at 61. It is not selected. AMD64 has not been built or tested.
The plugin manifest/signature is retained; no unsigned plugin configuration is
introduced. Signature acceptance for this unselected candidate is NOT VERIFIED.

Reproduce from the repository root (network and Docker required):

```sh
docker build --progress=plain -t evidenceai-grafana:experimental-m122 infra/monitoring/grafana-rebuild
docker build --progress=plain -f infra/monitoring/grafana-rebuild/opentsdb.Dockerfile -t evidenceai-grafana:m122 infra/monitoring/grafana-rebuild
```

Keep experiments separate from performance measurements. See
[12.2 assessment](../../../docs/security-remediation-12-2.md) for actual outcomes,
limitations, catalog/source evidence and release blockers.

## 12.3 verification additions

The core recipe now requires successful zero-fuzz dry-run **and actual** patching,
checks resolved kin-openapi/jsonschema versions, and records compiler, Go build
metadata, source archive/patch/module/binary SHA-256s in
`/usr/share/grafana/evidenceai-build.txt`. Its embedded commit identifies the
actual tag source, with an explicit experimental branch, rather than implying
parity with the vendor's unavailable patched commit. The recorded metadata is
local build evidence, **not** a vendor signature or independently verified
attestation. The dependency patch is unchanged.

`stackdriver.Dockerfile` installs the complete checksum-pinned official signed
Cloud Monitoring 12.6.3 plugin. Build against the pinned original image, or use
`--build-arg BASE_IMAGE=evidenceai-grafana:experimental-m123` to combine it with
the patched core. Actual ARM64 scans found all six Cloud Monitoring high findings
still present in the newer executable: plugin-only image 61 high; combined image
56 high. No unsigned-plugin setting or plugin removal is used. AMD64 checksums
are recorded for reproducibility but AMD64 builds/acceptance are NOT VERIFIED.

```sh
docker build --progress=plain -t evidenceai-grafana:experimental-m123 infra/monitoring/grafana-rebuild
docker build --progress=plain -f infra/monitoring/grafana-rebuild/stackdriver.Dockerfile -t evidenceai-grafana:plugins-m123 infra/monitoring/grafana-rebuild
docker build --progress=plain -f infra/monitoring/grafana-rebuild/stackdriver.Dockerfile --build-arg BASE_IMAGE=evidenceai-grafana:experimental-m123 -t evidenceai-grafana:combined-m123 infra/monitoring/grafana-rebuild
```

All 12.3 candidates remain unapproved and unselected. The isolated transition
fixture exercises restart, selected-to-custom upgrade and rollback with a
persistent synthetic dashboard; it does not authorize production downgrade or
establish complete source/vendor security parity. See the
[12.3 report](../../../docs/security-remediation-12-3.md) for final results.
