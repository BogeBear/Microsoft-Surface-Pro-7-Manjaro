# Contributing

Start with the current-status and source-map documents. Report the exact kernel, device model, revision and reproducible steps. Keep captures, biometric templates, personal logs, recovery keys and private signing material out of issues and commits.

Separate source review and synthetic tests from physical hardware evidence. A successful mock/VM test does not demonstrate sensor timing, optical exposure, illumination safety or secure identity recognition. Keep original timestamps, version bindings, failure receipts and shutdown evidence when investigating a hardware failure.

Changes to privileged helpers or drivers should have fault/ordering tests in an isolated VM without host mounts, network or physical passthrough before physical installation. Never bypass signature validation or use forced module loading. Review historical deployment scripts before adapting them.
