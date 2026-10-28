# Evidence snapshots

The large payloads in this directory are ignored by Git. Transfer them separately.
`index.json` records the snapshot manifest hash and bundle checksum.
Use `./scripts/drc archive verify` after transfer.

The initial snapshot is `2026-10-28/`. Original paths start under its `root/`.

- [Original PDFs](2026-10-28/root/output/pdf/)
- [Original PowerPoint and builder sources](2026-10-28/root/output/slides/)
- [Finished figures and report metadata](2026-10-28/root/docs/reports/)
- [Frozen campaigns and raw evidence](2026-10-28/root/reports/runs/)
- [All primary datasets](2026-10-28/root/test_data/)
- [Secondary generated datasets](2026-10-28/root/output/c2c3/)
- [Manifest](2026-10-28/manifest.json)

See `docs/PORTABLE_HANDOFF.md` for bundle creation, restore, configuration, and
report rebuild commands. Snapshot evidence is immutable. Use a new snapshot name
for later work. Use the Git checkout for the latest portable setup code; source
copies in the snapshot record the files present when preservation started.
