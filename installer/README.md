# Independent SP7 workbench installer

Version0.3.0 installs the pinned camera source and offline tests under
`/opt/sp7-research`. It is an **inactive research package**. It never installs
or loads kernel modules, opens cameras, adds privilege, changes autostart,
PAM/SDDM, firmware, Secure Boot, GRUB or Windows.

## Build and inspect

Use an ordinary user, Python3.11 or newer and a separate local checkout of the
exact camera source commit pinned in `build_package.py`:

```sh
python3 installer/build_package.py --camera-source /path/to/camera-checkout --output /path/to/new-output
python3 installer/sp7_setup.py check
python3 installer/sp7_setup.py plan --package /path/to/new-output/sp7-independent-workbench-0.3.0-x86_64.tar.gz --sha256 EXACT_PACKAGE_SHA256 --backup-root /path/to/verified-external/BACKUP/SP7-installer
```

The builder checks the exact camera SHA256SUMS file and each listed source
file. It refuses links, changed files, path escapes and existing output files.
It downloads no code, dependencies, firmware or pretrained models.
The plan validates the archive; the actual transaction additionally validates
external backup storage before changing any active release.

## Install, remove and restore

Installation supports only Manjaro x86_64 on Microsoft Surface Pro7 with
kernel `7.2.11-arch1-1-surface`, glibc2.38+ and Python3.11+. It refuses a
mismatch. Other Surface models need separately verified hardware profiles.

Install/uninstall/rollback use explicit administrator authorization and
`python3 -I installer/sp7_setup.py` followed by the corresponding command.
Use the same package, exact hash and verified external `--backup-root` used
for the plan. Backups must use a persistent separate USB filesystem or
supported network mount. RAM, an internal partition and an unverified
mount are refused. For an existing project, retain the owner's selected
external BACKUP destination; never silently move backups onto the SP7.
The installer does not set up network mounts, passwords or private keys.

Every mutation first writes and fsyncs a backup transaction. `status` reports
the active release. `uninstall` removes only unchanged managed files.
`rollback --transaction TRANSACTION_ID` restores a saved release only when
no later or unknown release has become active. Unknown edits and corrupted
backups stop the operation. Save the transaction ID and external backup.
A shared application lease blocks concurrent upgrades during offline tests.

`offline-tests` runs as an ordinary user and requires a C compiler and NumPy.
Actual model inference separately needs OpenCV and the exact externally
licensed UINT8 model/configuration. No camera or authentication operation
is part of these tests. Removing this package does not remove unrelated
historical research files or system drivers.

## Verification and limits

The exact source package was installed, fully checked, removed and restored
inside a disposable VM without networking, host mounts or device passthrough.
Root installer failure/ordering tests and ordinary-user image/recovery tests
are separate. Native C fixtures were compiled on the development host and
executed in the VM because its minimal image has no compiler. A VM-only
storage injection allowed a separate tmpfs fixture to stand in for network
storage; the production storage guard was not weakened. VM results do not
prove a physical driver installation or production authentication.

The old OV7251 derivatives, FP16 loader/weights, camera images, embeddings,
credentials and private conversations are absent. Linux-derived source retains
GPLv2; standalone userspace and installer code retain GPLv3. The independent
source remains experimental: persistent driver activation and a production
camera controller still need their own recovery-tested integration.

The optional nine-window RGB proposal candidate improves the second captured
sequence from17/30 to25/30 at the same threshold, with29/30 on the first.
This is exploratory analysis of the same two captures, not independent new
physical validation. No identity or full-field person-exclusion claim follows.
