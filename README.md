# ocsync

Secure sync for OpenCode and Oh My OpenAgent (OMO) configuration across machines.

`ocsync` keeps ordinary configuration snapshots in the existing central PostgreSQL store. Credentials follow a separate path: they are encrypted for each destination machine before leaving the source. The database and dashboard never receive or display plaintext credentials.

## What it syncs

Configuration is grouped into opt-in profiles:

| Profile | Paths under `~/.config/opencode` |
|---|---|
| `core` | `opencode.json`, `opencode.jsonc`, `.opencode/opencode.json` |
| `omo` | `oh-my-openagent.json`, `oh-my-openagent.json.migrations.json` |
| `plugins` | `.opencode/plugins/`, `plugins/` |
| `agents` | `agents/` |
| `skills` | `skills/` |

This is intentionally the entire sync scope: OpenCode config, OMO config, custom plugins, custom agents, custom skills and explicit encrypted OpenCode auth. Commands, TUI preferences, package manifests, `dcp.jsonc`, backups and `node_modules` are deliberately excluded. Select a subset with `--profiles core,omo`.

## Credential model

OpenCode credentials are stored locally in:

```text
~/.local/share/opencode/auth.json
```

They are **not** part of normal config sync. Credential sync is explicit (`--include-auth`) and works only after every destination machine has registered a public key.

- Each machine creates an RSA-3072 keypair at `~/.config/ocsync/identity.pem` (mode `0600`).
- The private key never leaves its machine.
- The source encrypts `auth.json` separately for every recipient public key using RSA-OAEP/SHA-256.
- PostgreSQL stores encrypted envelopes only.
- The dashboard shows only host metadata, key fingerprint and job state — never config contents or credentials.
- Decryption happens only on the destination machine, where `auth.json` is written mode `0600`.

Treat a credential push as a sensitive action: choose the recipients intentionally and only sync between trusted machines.

## Requirements

- Python 3.8+
- `openssl`
- SSH alias `vulcan`
- Remote `shared-postgres` container with the `memory_gateway` database

The v3 script creates its additional tables (`ocsync_hosts`, `ocsync_secret_envelopes`, `ocsync_jobs`) automatically. Existing `ocsync_configs` data remains compatible.

## Quick start

On **each trusted machine**:

```bash
ocsync init
```

Push standard configuration:

```bash
ocsync push
```

Push only OMO and core config:

```bash
ocsync push --profiles core,omo
```

Compare with a host without writing:

```bash
ocsync diff macbook-host --profiles core,omo,plugins
```

Pull config with an interactive confirmation:

```bash
ocsync pull macbook-host --profiles core,omo
```

## Credential sync

After every target has run `ocsync init`, the source can create recipient-specific encrypted envelopes:

```bash
ocsync push --include-auth --auth-recipients desktop-host,laptop-host
```

On a destination, apply config plus its encrypted credential envelope:

```bash
ocsync pull source-host --profiles core,omo --include-auth
```

The credential value is never printed or shown in a diff.

## Local dashboard and queued sync

Start the dashboard on the machine hosting your browser session:

```bash
ocsync serve
# http://127.0.0.1:8787
```

It is local-only by default. It lets you inspect registered hosts, config counts, key fingerprints and queue a selected source → target sync job. It cannot directly write files on another host.

On each target machine, run the local agent when you want it to process queued work:

```bash
ocsync agent
```

The target executes its own pull locally. This prevents the web UI/server from gaining remote filesystem write authority.

## Commands

```text
ocsync init
ocsync push [--profiles core,omo,...] [--include-auth --auth-recipients host1,host2]
ocsync diff [source-host] [--profiles core,omo,...]
ocsync pull [source-host] [--profiles core,omo,...] [--include-auth]
ocsync status
ocsync serve [--host 127.0.0.1] [--port 8787]
ocsync agent
```

## Security notes

- Do not expose `ocsync serve` directly to a LAN or the internet. The dashboard has no login layer because it is intentionally bound to `127.0.0.1` by default.
- Do not add `.env`, arbitrary file paths, private keys or browser profile files to profiles.
- Config snapshot data is still plaintext in PostgreSQL by design. Keep the database private and limit sync profiles to non-secret configuration.
- Auth is encrypted at rest in PostgreSQL, but anyone holding a destination machine's private key can decrypt envelopes intended for it.
- Existing queued jobs are executed only after `ocsync agent` runs locally on the target machine.

## License

MIT © 2026 lear-ZLC

## Legacy v2

v2 synced only a small, hardcoded set of files and stored all selected content in the `ocsync_configs` table. v3 keeps that table for non-secret config while adding profile selection, OMO support, host identity registration, recipient-specific auth envelopes and a local queue dashboard.
