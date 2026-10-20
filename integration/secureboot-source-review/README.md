# Upstream sources consulted

The adjacent Linux keyring and shim MOK excerpts retain their upstream notices and licenses. They are reference excerpts, not a buildable independent bootloader.

The original checkout also contained a relative symlink pointer to linux-surface's `patches/7.2/0001-secureboot.patch`. This export does not include that dangling pointer as if it were a patch. Obtain the actual patch from the matching [linux-surface revision](https://github.com/linux-surface/linux-surface/tree/master/patches) and verify it against the exact kernel revision before use.
