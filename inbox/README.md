Drop one file per edition: `YYYY-MM-DD.json`. The file name is the edition date.

The bot POSTs that JSON to the ingest Worker, which commits this file. You can also commit it yourself. GitHub Actions runs `apply_packet.py`, rebuilds the site, and publishes Pages.

The shape is in `data/SCHEMA.md`. `docs/examples/1941-12-07-pearl-harbor.json` is a sample packet. Do not copy it here.
