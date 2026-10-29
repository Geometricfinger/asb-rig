"""Ordered, append-only schema migrations. Never edit a shipped migration; add a new one.
The DB records `PRAGMA user_version`; startup applies anything newer inside a transaction."""
MIGRATIONS: list[tuple[int, str]] = [
    (1, """
    CREATE TABLE session(id TEXT PRIMARY KEY, t_wall REAL, consent_id TEXT, site_code TEXT, gps_policy TEXT);
    CREATE TABLE audit_log(id INTEGER PRIMARY KEY, t_wall REAL, kind TEXT, detail TEXT);
    CREATE TABLE signature_event(id TEXT PRIMARY KEY, t_wall REAL, code TEXT, level TEXT, score REAL, body BLOB);
    CREATE TABLE fusion_result(id INTEGER PRIMARY KEY, t_wall REAL, anomaly_index REAL, body BLOB);
    """),
    (2, """
    CREATE TABLE sighting(sighting_id TEXT PRIMARY KEY, t_wall REAL, codes TEXT, body BLOB, verdict TEXT,
        chain_idx INTEGER, h_prev BLOB, h_this BLOB, keep INTEGER DEFAULT 0);
    CREATE TABLE sweep(sweep_id TEXT PRIMARY KEY, site_code TEXT, t_wall REAL, t_end REAL, body BLOB, outcome TEXT, keep INTEGER DEFAULT 0);
    CREATE TABLE site(site_code TEXT PRIMARY KEY, name TEXT, anchors TEXT);
    CREATE TABLE emitter_baseline(site_code TEXT, emitter_key TEXT, features_json TEXT, n_windows INTEGER, built_utc REAL,
        PRIMARY KEY(site_code, emitter_key));
    CREATE TABLE emitter_drift(emitter_key TEXT, t_wall REAL, changed_features TEXT, windows INTEGER);
    """),
    (3, """
    CREATE TABLE eye_trace(run_id TEXT, t_wall REAL, t_mono_ns INTEGER, pupil_mm REAL, blink INTEGER, glint_n INTEGER,
        glint_offset_px REAL, glint_code_ok INTEGER, quality REAL);
    CREATE TABLE voice_event(run_id TEXT, t_wall REAL, prompt_id TEXT, spoof_score REAL, embed_sim REAL, enrolled INTEGER);
    CREATE TABLE enrollment(subject_code TEXT, kind TEXT, embedding_enc BLOB, created_utc REAL, delete_after_utc REAL);
    CREATE TABLE golden_clip(clip_id TEXT PRIMARY KEY, split TEXT, label TEXT, sha256 TEXT, source_sighting TEXT,
        consent_ok INTEGER, manifest_version INTEGER);
    CREATE TABLE chain_anchor(idx INTEGER PRIMARY KEY, head BLOB, sig BLOB);
    """),
]
LATEST = MIGRATIONS[-1][0]
