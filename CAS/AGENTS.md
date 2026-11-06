# CAS: rules for agents

Sigurd works with agents on more than one PC. Git and the register are the only shared state.

## The register is the base layer

`Outstanding items.xlsx` is the agreed state. Its `Decision / answer` column wins over code, FDs, branches and
your own earlier reasoning.

- Before CAS work: `git pull` here, and check recent commits in `scaleaq/heimdall-plc` (all branches),
  `heimdall-cas-simulation` and `heimdall-cas-hmi`. Read the register entries changed since your last session.
- If code, an FD or a branch contradicts the register: **stop and ask Sigurd**. Do not change the code, the FD or
  the register to make them agree.
- Do not implement something the register has decided against, or not decided yet. Ask first.
- When something is decided, write it in the register (Decision / answer, Decided date) in the same session.
