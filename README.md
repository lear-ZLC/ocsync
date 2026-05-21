# ocsync

**Sync your OpenCode configs across machines via a central PostgreSQL store.**

`ocsync` is a lightweight Python utility designed to synchronize [OpenCode](https://opencode.ai) configuration files, plugins, custom agents, skills, and credentials between multiple machines using a central PostgreSQL database accessed securely over SSH.

## 🚀 Features

- **Auto-discovery**: Automatically finds and syncs standard OpenCode configuration paths.
- **Base64 Encoding**: Safe transport of binary or special character data via Base64.
- **Diff Before Apply**: Review changes with a side-by-side diff before overwriting local files.
- **Interactive Resolution**: Choose which host to pull from and confirm updates.
- **SSH/Tailscale Native**: Works anywhere you have SSH access; no local network discovery or complex setup needed.
- **Zero Dependencies**: Single-file script using only the Python standard library.

## 🛠 Architecture

```text
  [ Local Machine ]             [ Remote Server ]
  |               |             |               |
  | ocsync push --|---- SSH --->| docker exec   |
  |               |             |   psql        |
  | ocsync pull <-|---- SSH ----|     |         |
  [               ]             [ PostgreSQL DB ]
```

The script connects to your database by wrapping `psql` commands inside an `ssh` call, typically targeting a PostgreSQL instance running in Docker on a management host (like Vulcan).

## 📋 Prerequisites

- **Python 3.8+**
- **SSH access** to a host that can reach your PostgreSQL database.
- **PostgreSQL** table initialized (see Configuration).
- The `psql` client installed on the remote host (or available via `docker exec`).

## 📥 Installation

```bash
curl -L https://github.com/ogzhnozlci/ocsync/raw/main/ocsync -o ocsync
chmod +x ocsync
sudo mv ocsync /usr/local/bin/ocsync
```

## ⚙️ Configuration

### Database Setup

Run the following SQL on your PostgreSQL instance to create the required table:

```sql
CREATE TABLE ocsync_configs (
    id SERIAL PRIMARY KEY,
    hostname TEXT NOT NULL,
    filepath TEXT NOT NULL,
    content TEXT,
    checksum TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(hostname, filepath)
);
```

### Script Customization

Edit the `ocsync` script to match your environment:

1.  **SSH Target**: Update the `pg()` function's `ssh` command to point to your DB host (default is `vulcan`).
2.  **Sync Items**: Modify the `SYNC_ITEMS` list to include or exclude specific directories/files:
    ```python
    SYNC_ITEMS = [
        "opencode.json",
        ".opencode/plugins",
        "skills",
        # Add your custom paths here
    ]
    ```

## ⚡ Quick Start

- **Check status**: See which hosts have pushed configs and when.
  ```bash
  ocsync status
  ```
- **Push changes**: Upload your local config to the central store.
  ```bash
  ocsync push
  ```
- **Pull changes**: Download and apply config from another machine.
  ```bash
  ocsync pull
  ```
- **Compare**: See differences between your machine and a remote host without applying.
  ```bash
  ocsync diff [hostname]
  ```

## 📄 License

MIT © 2026 ogzhnozlci
