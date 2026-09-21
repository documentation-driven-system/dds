# examples/broken

A deliberately INVALID `.dds/` tree. It exists so that `python .dds/meta/scripts/dds.py check` has a permanent negative test:
every defect below MUST be reported, and `tests/test_dds.py` fails if one goes missing.

Run it yourself:

```bash
python .dds/meta/scripts/dds.py --root examples/broken check --gate
```

`EXPECTED.txt` lists one error substring per line; `EXPECTED_WARN.txt` lists expected warnings. Since 2.1.0 the fixture also carries a reversed dependency with a cycle (`architecture/core-db.dds.md` ↔ `modules/stray.dds.md`), an empty tagged section, and `sources:` globs that match nothing.
Do not fix these files. Add a defect here whenever a new ENFORCED rule lands in `schema.dds.md`.
