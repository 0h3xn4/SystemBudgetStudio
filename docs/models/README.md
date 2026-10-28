# Models, rules and assumptions

One page per model, rule and assumption, written for systems engineers: the equation or logic, the symbols and their units, the inputs and where each comes from, the source (or an honest "source to be supplied"), the simplifications and their size, and how to change or replace it. The pages are written in the same step as the feature that makes the model visible in the tool; this index lists what exists and what is planned.

The plan and the reasons are in the [transparency audit](../transparency_audit.md#7-prioritized-implementation-plan). Where the tool deviates from a textbook model, the numbered deviations (DV-*) in [DEVIATIONS.md](../DEVIATIONS.md) remain the record; a page here explains the model, a deviation records the difference.

| Area | Page | Status |
|---|---|---|
| Static power budget | [power-static.md](power-static.md) | written |
| How a number was obtained (`budget explain`) | [explain.md](explain.md) | written for static power, mass and thermal |
| Time-domain power (array, battery, modes, edges) | (planned) | planned |
| Orbit, eclipse and Sun geometry (gravity models, shadow models) | (planned) | planned |
| Mass budget (margins, centre of mass, inertia, expendables) | [mass-static.md](mass-static.md) | written |
| Thermal (network, steady state, environment) | [thermal-static.md](thermal-static.md) | written |
| RF link (EIRP, G/T, losses, rate selection, volume) | (planned) | planned |
| Units and conversions (accepted units, canonical units, refused words) | (planned) | planned |
| Rounding and number formats | (planned) | planned |
| Provenance, input digest and `budget verify` | [provenance.md](provenance.md) | written |
