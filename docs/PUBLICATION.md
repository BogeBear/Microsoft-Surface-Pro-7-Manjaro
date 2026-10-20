# Scope of the 2026-10-20 source release

This release contains project source, relevant integration configuration, synthetic tests, documentation and selected technical test-log extracts. It does not contain private conversations, agent instructions, internal handoff notes, face photographs, raw captures, embeddings, calibration measurements, recovery material, private keys, system backups, Windows installation media, VM disks, firmware binaries or downloaded neural-network models.

`docs/source-index.json` maps exported source files to project-relative development locations. Operational paths, usernames, LAN addresses and public-key literals were replaced with examples. Hardware/API GUIDs and upstream copyright notices retain their meaning. File hashes in the index describe the export stage; `SHA256SUMS` is the final public-file manifest.

The export is a source adaptation, not the original deployed package. Private frozen originals and test receipts are retained unchanged. Their successful tests are historical evidence for those originals, not a claim that every adapted historical script has been re-tested. The release's own offline test log records the tests actually repeated on the public copy.

Historical scripts intentionally retain version/hash/checkpoint gates. Missing installation manifests and opaque generated payloads are not reconstructed from private device data. They are audit recipes, not a universal installer. Do not run an entire source directory as a batch.
