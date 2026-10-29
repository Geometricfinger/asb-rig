# asb.headless — M-09
Runs the full pipeline with sim or replay adapters, a virtual clock, sockets blocked and an LED stub. `run_scenario`, `run_replay`, `record_clip`. Output is rounded and deterministic so `golden/expected/*.json` can be compared byte-for-byte (E-23).
