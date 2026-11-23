# unifi-family

A small CLI over the official **UniFi Network Integration API** (v11.0.97) for
allowing/blocking websites on specific devices — built for managing a family's
devices.

## Install

Uses [uv](https://docs.astral.sh/uv/). The script declares its own
dependencies inline (PEP 723), so there's nothing to install separately — `uv`
fetches them on first run into an isolated environment.

```bash
# run it directly
uv run --script unifi-family --help

# or put it on your PATH (the shebang runs it via `uv run`)
chmod +x unifi-family
ln -s "$PWD/unifi-family" /usr/local/bin/unifi-family
unifi-family --help
```

(If you don't have uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`.)

## Connect

Two ways to reach the gateway:

**Cloud (recommended — works from anywhere):**
1. Sign in at https://unifi.ui.com → **Settings → API Keys**, create a key
   (enable write access for firewall edits).
2. Find your console id: `curl -s https://api.ui.com/v1/hosts -H 'X-API-KEY: KEY'`
3. Save it:
```bash
unifi-family config --base-url https://api.ui.com \
  --api-key YOUR_KEY --console-id <CONSOLE_ID>
```

**Local console (LAN only):**
```bash
unifi-family config --base-url https://192.168.1.1 --api-key LOCAL_KEY
```
(local keys are made in the Network app → Control Plane → Integrations)

Settings are written to `~/.config/unifi/config.json` (chmod 600). Env vars
`UNIFI_BASE_URL` / `UNIFI_API_KEY` / `UNIFI_SITE` also work.

## Inspect what's on the network

```bash
unifi-family sites                      # list sites
unifi-family clients                    # name, MAC, IP of everything connected
unifi-family clients laptop             # filter
unifi-family devices                    # rich detail: maker, hostname, AP, first/last seen
unifi-family zones                      # firewall zones
unifi-family dpi-categories vpn         # DPI category ids (for --app-category)
```

`devices` is the one to use when figuring out which client is whose — it shows
each client's maker/OUI, hostname, which access point (room) it's near, and
whether its MAC is randomized.

## Members (map a person to their devices)

Members are a **local** convenience stored in `~/.config/unifi/members.json`
(they are not pushed to UniFi). Attach devices to a person, then use that name
anywhere a device is expected (`block`, `review`) and it expands to all their
MACs.

```bash
unifi-family members list                         # list members + devices, grouped
unifi-family members add alex kid                 # create a member (optional group: kid/adult)
unifi-family members add robin adult
unifi-family members alex add "Alex Laptop"       # attach a device (by name/MAC/IP)
unifi-family members alex add 6a:23:fb:dc:d7:0a   # attach by MAC
unifi-family members alex                         # show alex's devices
unifi-family members alex remove "Alex Laptop"    # detach a device
unifi-family members delete alex                  # remove the member

# Use a member name directly:
unifi-family review alex
unifi-family block alex --domain reddit.com

# Target ONE device of a member with member:filter (matches device name):
unifi-family block alex:laptop --domain tiktok.com
unifi-family review alex:phone
```

## Block / allow

```bash
# Block domains for a device (matched by name, MAC, IP, or member):
unifi-family block "Alex Laptop" --domain tiktok.com --domain youtube.com

# Block a whole DPI category, e.g. VPN/proxy (id 11):
unifi-family block "Alex Laptop" --app-category 11

# Allow-list a site (ALLOW rule, evaluated before blocks):
unifi-family block --allow "Alex Laptop" --domain khanacademy.org

# Preview the payload without sending it:
unifi-family block "Alex Laptop" --domain tiktok.com --dry-run
```

## Custom times (per device, per person)

Any `block` can be scoped to a time window, specific weekdays, a date range, or
a single day:

```bash
# Daily window (block 8pm–7am every day):
unifi-family block alex:laptop --domain roblox.com --start 20:00 --stop 07:00

# School nights only (weekdays), overnight:
unifi-family block alex:laptop --app-category 8 --days weekdays --start 20:00 --stop 07:00

# Weekends all day:
unifi-family block alex:laptop --domain tiktok.com --days weekends

# Specific days and a time window:
unifi-family block alex:laptop --domain youtube.com --days mon,wed,fri --start 16:00 --stop 18:00

# A date range (e.g. exam period):
unifi-family block alex:laptop --domain discord.com \
  --start-date 2026-12-01 --stop-date 2026-12-15

# One-time only, for a single date:
unifi-family block alex:laptop --domain x.com --date 2026-12-25
```

Scheduling flags:
- `--start HH:MM --stop HH:MM` — active time window (24h; can cross midnight)
- `--days` — `mon,tue,…` or `weekdays` / `weekends` / `everyday`
- `--start-date / --stop-date YYYY-MM-DD` — a custom date range (`CUSTOM`)
- `--date YYYY-MM-DD` — one time only (`ONE_TIME_ONLY`)

Each rule applies only to the device(s) you target, so every device for every
person can carry its own set of blocks on its own schedule.

## See and manage the rules

```bash
# Effective rules affecting a device/member, in evaluation order:
unifi-family review alex
unifi-family review alex --all          # include every zone pair

unifi-family policies list
unifi-family policies get <id>
unifi-family policies rename <id> "New name"
unifi-family policies add-domain <id> twitch.tv
unifi-family policies rm-domain <id> twitch.tv
unifi-family policies set-domains <id> a.com b.com
unifi-family policies disable <id>      # toggle off without deleting
unifi-family policies enable <id>
unifi-family policies delete <id>
```

## How "block" maps to UniFi

It creates a **zone-based firewall policy**:

- **action**: `BLOCK` (or `ALLOW` with `--allow`)
- **source**: the `Internal` zone, filtered to the device MAC(s)
- **destination**: the `External` zone, filtered to the given domain(s) or DPI
  app-category(ies)
- **ipProtocolScope**: IPv4 + IPv6
- optional **schedule** via `--start/--stop`, `--days`, `--date`, or a date range

If your zones aren't named `Internal`/`External`, pass `--source-zone` /
`--dest-zone` (see `unifi-family zones`).

## Rule ordering

UniFi evaluates policies by ascending `index`, and the **first matching rule
wins**. `unifi-family review <device>` prints the effective order (allow-list
first, then blocks, then the default deny) so you can see exactly what a device
can and can't reach, and when.

> Note: domain/app matching uses DPI/SNI. HTTPS with encrypted SNI, DoH, or a
> VPN can evade pure domain rules. Blocking the "Tunneling and proxy services"
> DPI category (`--app-category 11`) stops most VPN/proxy apps, but a device the
> user fully controls can never be 100% locked down by the network alone —
> combine with on-device controls (MDM / Screen Time) for airtight control.
