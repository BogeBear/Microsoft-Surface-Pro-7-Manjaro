# Independent camera replacement integration boundary

Status: experimental source checkpoint, 2026-11-02. This is not an installable face-authentication release.

The exact camera source checkpoint is [876b5b1dbb5125d5ff878ff5b2d2671b2716e8e8](https://github.com/BogeBear/Microsoft-Surface-Pro-7-Face-ID/tree/876b5b1dbb5125d5ff878ff5b2d2671b2716e8e8/replacement), proposed in [camera pull request 1](https://github.com/BogeBear/Microsoft-Surface-Pro-7-Face-ID/pull/1).

## Replacement scope

The sensor retains the GPLv2 linux-surface baseline and attribution. Newly written gate/lifecycle code replaces the inherited uncertain-license OV7251 additions. The standalone GPLv3 detector accepts only the exact separately reviewed TensorFlow UINT8 model/configuration bytes. Historical OV7251 derivatives, Caffe FP16 loading/fallback, pretrained weights, firmware and private images are excluded from that source checkpoint. Prior exposure to older code is disclosed; no untouched clean-room or legal-certification claim is made.

## What was checked

- Exact7.2.11-arch1-1-surface module build and normal module load/unload in an isolated VM.
- Fault/ordering, status/model-byte, private RAM cleanup and recovery contracts, with separate ordinary-user and root VM execution.
- Physical30RGB+30IR object capture. Its original coordinator failed because it applied a metadata-only closure validator to raw capture; corrected raw/kernel validation and separate actual recovery are recorded without rewriting the failure.
- A successful120IR+30RGB descriptor-only watchdog trial using output-direction3005:3, frame-trigger3b80:4 and STROBE-source3b96:7 enables. The requested deadline stays3seconds; observed closure is not a hard real-time or optical pulse-power guarantee.
- Exact original format/crop/control/graph restoration, native/kernel/root closure and independent complete eight-device idle checks. Private raw files were hash/fsync-exported and removed from SP7 RAM.

See the pinned camera checkpoint's replacement/TEST-EVIDENCE.json and replacement/PHYSICAL-EVIDENCE.json. Object visibility and model proposals do not establish live-person identity, PAD, stereo depth or a validated login threshold.

## Integration and rollback work still required

Operational controllers must migrate the new module identity, ir_control/ir_snapshot API, three-gate readbacks and complete shutdown contract together. The read-only ir_strobe_test compatibility view does not restore the old writer. Mixing an old controller or historical build recipe with the new module is outside the tested boundary.

The [inactive workbench installer](../installer/README.md) now provides version-checked source installation, upgrade, uninstall and rollback with external backups. It was exercised in an isolated disposable VM. It does not install or activate camera drivers, change authentication or update historical dual-boot workflows. Persistent driver activation and a production camera controller still require a separately tested transaction.

The current hardware target is Microsoft Surface Pro7 with the exact tested kernel ABI. Additional Surface models require their own DMI/hardware/kernel profiles and actual evidence. The experimental module defaults to refusing hardware probing without explicit opt-in; no unattended camera, PAM/SDDM login or biometric approval is enabled by this checkpoint.

## Licensing and privacy

Linux-derived sensor code remains GPLv2; standalone project userspace remains GPLv3; model publisher terms are separate. No training-data rights are inferred. The original pending upstream license question remains relevant to the preserved historical material, which is not part of the new camera delivery.

Only source, licenses and sanitized verification summaries are referenced. No private conversations, face images, embeddings, recovery keys, SSH/signing keys or model binaries are published by this update.


## Two new captures

Two separate actual presence confirmations led to two successful new captures,
30RGB+30IR frames each. Both original coordinators passed with no errors and
complete native/kernel/root closure, exact configuration restoration and an
independent eight-device idle check. Private files were hash/fsync-exported
and removed from device RAM. No images or biometric vectors are published.

Fixed-orientation filtering gave one diagnostic proposal in14/14 brighter IR
frames in each capture. A central RGB proposal window gave29/30 and17/30;
this remains insufficient for a login reliability claim. There is no identity
match, geometric calibration, negative-participant study or verified PAD.
