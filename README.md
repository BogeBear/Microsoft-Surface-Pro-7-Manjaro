# Microsoft Surface Pro 7 — Manjaro integration

Source and configuration for the project's Manjaro setup on Surface Pro 7, alongside a preserved Windows 11 installation using Secure Boot and a readable GRUB menu.

**This repository documents a working project installation and its integration recipes. It is not a downloadable operating-system image or a universal unattended installer.** Paths, disk identities and host details in historical scripts have been replaced with examples. Review and adapt them before use.

## Current state — 2026-10-20

- Manjaro desktop restored alongside Windows 11; both boot selections were checked on the test SP7.
- Signed boot-chain integration and an enrolled linux-surface key were used while retaining Secure Boot.
- GRUB menu enlarged for readability, with Windows, Manjaro text/control and desktop choices.
- Wi-Fi firmware recovery, SSH transport helpers, desktop widgets and network/audio menu repairs are included as source workflows.
- Touch/tablet and on-screen keyboard integration remain part of the complete system project; this source snapshot does not claim independent coverage of every peripheral.
- RGB/IR driver and face-interface development lives in the [camera companion repository](https://github.com/BogeBear/Microsoft-Surface-Pro-7-Face-ID). Secure face authentication / PAD is not completed or activated.

## Contents

| Path | Purpose |
|---|---|
| `integration/host-workflow` | Historical host-side preflight, backup/restore, Windows-volume shrink, partition/boot-chain and desktop repair recipes |
| `integration/usb-overlay` | Temporary live-system SSH helper and boot configuration examples |
| `integration/secureboot-candidate` | Embedded boot configuration example |
| `integration/secureboot-source-review` | Upstream source excerpts used for review, retaining their own licenses |
| `integration/readable-grub-candidate` | Enlarged menu and Windows boot-chain configuration |
| `integration/reboot-policy` | Temperature/reboot policy and synthetic tests |
| `integration/workbench` | Development-host workflow tooling |

## Before adapting a workflow

The scripts were designed for one staged restoration with explicit version, boot, checkpoint and disk-identity gates. They are published for review, not as a run-all installer. Several modify partitions, encrypted Windows boot state or EFI files. Use a verified external backup, record the actual partition map, keep the BitLocker recovery key available privately and validate the Windows boot entry before changing defaults.

No recovery keys, private signing keys, installed-machine images, firmware binaries, OS backups, private chats or account configuration are shipped. Do not use example disk IDs as real targets. Never disable existing checks just to make an old script run.

See [publication scope](docs/PUBLICATION.md), [workflow map](docs/WORKFLOWS.md), [licensing](THIRD_PARTY.md), [contributing](CONTRIBUTING.md) and [security/privacy](SECURITY.md).


## Independent camera replacement checkpoint — 2026-11-02

The camera project now has an [experimental independent source checkpoint](https://github.com/BogeBear/Microsoft-Surface-Pro-7-Face-ID/tree/876b5b1dbb5125d5ff878ff5b2d2671b2716e8e8/replacement) on a separate review branch. It replaces the inherited uncertain-license OV7251 additions with a new GPLv2 lifecycle layer on the licensed Linux baseline and uses a hash-bound UINT8 proposal backend without Caffe FP16 weights.

Physical object and two new presence-authorized face captures, plus bounded three-gate timer evidence, are recorded there. The [inactive workbench installer](installer/README.md) provides VM-tested source installation, upgrade, uninstall and rollback. Persistent driver installation, production controller migration and authentication/PAD validation remain pending. See [the integration boundary](docs/INDEPENDENT-CAMERA-REPLACEMENT.md) before adapting the source. The historical system workflows above remain a distinct snapshot.

