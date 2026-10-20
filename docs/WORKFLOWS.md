# Workflow map and limitations

The project first used a temporary signed Linux USB environment to inspect the device, preserve Windows, shrink its volume through Windows, restore Manjaro only into the intended space and establish a signed boot chain. Windows chainloading was corrected so the firmware's original Windows Boot Manager / BCD remained the authoritative path. The readable menu keeps a text-mode Linux recovery/control entry.

Published configuration contains examples rather than the original disk identities. Key enrollment, Windows recovery/PIN/Hello restoration and physical boot verification required local user participation. A source copy cannot repeat those steps automatically or prove a different machine's encryption state.

The test device used a Surface kernel, matching firmware and matching signed modules. One temporary live boot lacked the Intel AX201 firmware and therefore exposed only loopback despite enabled Wi-Fi; the correct firmware restored the interface. Firmware itself must come from its upstream/distribution package and license, not this repository.

Desktop repairs include the restored KDE widgets and the network/audio menus. Their source and configuration recipes are separate from camera code. Do not activate experimental face/PAM integration from a desktop repair script.

`tools/check_sources.py` checks Python syntax and Bash/POSIX-shell syntax without executing the operational scripts. This is a packaging check, not a partition/boot simulation or proof of hardware compatibility. The source map and final file hashes support review; historical gates, private manifests and actual recovery material are deliberately not supplied.
