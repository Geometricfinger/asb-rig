# oiris.store — C4
`db` (SQLite, versioned migrations, sealed JSON bodies, audit log), `migrations` (append-only), `sightings` (SightingLog with GPS policy, hash chain, export rounding, map pins + OSM attribution; SweepTimeline). **Depends on**: `oiris.security`, `oiris.guard`. Extend by appending a migration.
