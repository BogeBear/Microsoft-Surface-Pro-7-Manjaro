# Licensing and upstream attribution

The repository's original project source is offered under the existing GPL version 3 license in `LICENSE`, except components with their own license notices. A top-level license does not replace upstream terms.

- Linux kernel/media/INT3472 and Intel IPU4 sources, including derived project changes, retain their SPDX/copyright notices and GPL version 2 terms. `GPL-2.0` is the older SPDX spelling; do not assume these files have been relicensed to GPLv3. Some UAPI headers use the Linux syscall-note exception.
- Files explicitly carrying an MIT notice retain that license. The HAL UI is in the camera companion repository. Some Intel interface headers also carry MIT notices.
- The shim MOK review excerpt retains Peter Jones / Red Hat attribution and `BSD-2-Clause-Patent` licensing.
- Full license/exception texts are provided under `LICENSES/`; existing in-file notices are authoritative for each file.

Upstream references:

- [linux-surface](https://github.com/linux-surface/linux-surface) and [Surface kernel](https://github.com/linux-surface/kernel)
- [SP7 IPU4 port](https://github.com/thisiscamk/sp7-ipu4-camera), [ruslanbay IPU4 work](https://github.com/ruslanbay/ipu4-drivers) and [Intel camera sources](https://github.com/intel/intel-camera-drivers)
- [Linux kernel](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/)
- [shim](https://github.com/rhboot/shim)
- [SPDX license texts](https://github.com/spdx/license-list-data)

Windows SDK headers and an upstream Microsoft sample used during research are not redistributed in this release. The project's own Windows reference tooling remains included. Firmware, Microsoft recovery media, models and Python/Qt/OpenCV/dlib binaries are not vendored; obtain them upstream under their respective licenses. A model's diagnostic use does not imply permission to redistribute its training data or a claim of secure biometrics.

## Kernel-facing project changes

Project changes to Linux/Intel drivers and their kernel-derived fault/ordering harnesses and kernel patches are distributed under GPL version 2, alongside their upstream code. They are outside the default GPLv3 scope of standalone project userspace tools. MIT-marked files retain MIT terms. Independent userspace programs using Linux UAPI are separate components, not a relicensing of the kernel.

Some historical source experiments duplicate earlier driver revisions for comparison. Their in-file license/copyright notices remain intact. The phrase "Intel proprietary tiled format" in a GPL-licensed interface header describes a pixel format; it does not itself change that header's GPL license. Binary firmware is excluded.

No rights to third-party trademarks, model training data or proprietary firmware are granted by this repository's license.
