# oiris.scores — score port (C1)
**Purpose**: one module per signal, `update(window) -> Score` with value/confidence in [0,1] and a health flag. **Inputs**: samples whose capability is in `inputs`. **Outputs**: `Score`. **Depends on**: `oiris.features`. Every call goes through `base.safe_update` (exceptions/NaN → FAILED).
**Extend**: implement the protocol, register under port `score`, map it to a family in `fusion/stack.SCORE_FAMILY`.
