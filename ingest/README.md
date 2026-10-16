# Ingest

`POST /inbox` on `https://gia-ingest.bryan-a4a.workers.dev` commits one packet as `inbox/YYYY-MM-DD.json` on `main`. Publish checks the packet and updates the site.

The Worker is already deployed from `src/index.js`. It rejects every POST until two secrets exist. Set them in the Cloudflare dashboard under Workers & Pages → gia-ingest → Settings → Variables and Secrets. Do not commit them, and do not paste them into chat.

1. Create a GitHub fine-grained personal access token. Resource owner `bmgcyber`, repository access only `intel-gia`, permission Contents read and write. Nothing else.
2. Add secret `GITHUB_TOKEN` with that token.
3. Run `openssl rand -hex 32`. Add secret `INGEST_SECRET` with that value. Put the same value in the Grok bot prompt.

The bot sends the raw JSON:

```bash
curl -X POST https://gia-ingest.bryan-a4a.workers.dev/inbox \
  -H "Authorization: Bearer $INGEST_SECRET" \
  -H "Content-Type: application/json" \
  --data-binary @packet.json
```

`200` and `"status": "filed"` means the file is on `main`. `"unchanged"` means those exact bytes were already there. `503` means a secret is missing. A bad packet can still be filed; Publish is the checker. POST the same edition again to replace it.

The token expires on the date you picked. Replace `GITHUB_TOKEN` before that date.
