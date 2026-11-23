# unifi-family

A small CLI over the official **UniFi Network Integration API** (v11.0.97) for
allowing/blocking websites on specific devices — built for managing kids'
devices.

## Install

```bash
cd unifi-cli
pip install -r requirements.txt
# optional: symlink onto your PATH
ln -s "$PWD/unifi-family" /usr/local/bin/unifi-family
```

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

## Everyday use

### Members (map a person to their devices)

Members are a local convenience stored in `~/.config/unifi/members.json`. Once a
person has devices attached, you can use their name anywhere a device is
expected (`block`, `review`), and it expands to all their MACs.

```bash
unifi-family members list                        # list members + devices
unifi-family members add naveen                  # create a member
unifi-family members naveen add "Naveen"          # attach a device (by name/MAC/IP)
unifi-family members naveen add "Kids iPad"       # attach another
unifi-family members naveen                       # show naveen's devices
unifi-family members naveen remove "Kids iPad"    # detach a device
unifi-family members delete naveen               # remove the member

# Then use the member name directly:
unifi-family review naveen
unifi-family block naveen --domain reddit.com

# Target ONE device of a member with member:filter (matches device name):
unifi-family block naveen:ipad --domain tiktok.com
unifi-family review naveen:mbp
```

### Custom times (per device, per person)

Any `block` can be scoped to a time window, specific weekdays, a date range, or
a single day:

```bash
# Daily window (block 8pm\u20137am every day):
unifi-family block naveen:ipad --domain roblox.com --start 20:00 --stop 07:00

# School nights only (weekdays), overnight:
unifi-family block naveen:ipad --app-category 8 --days weekdays --start 20:00 --stop 07:00

# Weekends all day:
unifi-family block naveen:ipad --domain tiktok.com --days weekends

# Specific days:
unifi-family block naveen:ipad --domain youtube.com --days mon,wed,fri --start 16:00 --stop 18:00

# A date range (e.g. exam period), optionally limited to weekdays/time:
unifi-family block naveen:ipad --domain discord.com \
  --start-date 2026-12-01 --stop-date 2026-12-15

# One-time only, for a single date:
unifi-family block naveen:ipad --domain x.com --date 2026-12-25
```

Scheduling flags:
- `--start HH:MM --stop HH:MM` \u2014 active time window (24h; can cross midnight)
- `--days` \u2014 `mon,tue,...` or `weekdays` / `weekends` / `everyday`
- `--start-date / --stop-date YYYY-MM-DD` \u2014 a custom date range (`CUSTOM`)
- `--date YYYY-MM-DD` \u2014 one time only (`ONE_TIME_ONLY`)

Each rule applies only to the device(s) you target, so every device for every
person can carry its own set of blocks on its own schedule. Use
`unifi-family review <device|member|member:filter>` to see the effective
allow/block list and the exact times.

```bash
unifi-family sites                      # list sites
unifi-family clients                    # name, MAC, IP of everything connected
unifi-family clients ipad               # filter
unifi-family zones                      # firewall zones
unifi-family dpi-categories vpn         # DPI category ids (for --app-category)

# Block domains for a device (matched by name, MAC, or IP):
unifi-family block "Kids iPad" --domain tiktok.com --domain youtube.com

# Block a whole DPI category, e.g. VPN/proxy (id 11):
unifi-family block "Kids iPad" --app-category 11

# Only during set hours each day (e.g. block games 9pm–7am):
unifi-family block "Kids iPad" --domain roblox.com --start 21:00 --stop 07:00

# Allow-list instead of block:
unifi-family block --allow "Kids iPad" --domain khanacademy.org

# Multiple devices in one rule:
unifi-family block "Kids iPad" "Kids Laptop" --domain tiktok.com

# See every rule affecting a device, in the order the firewall evaluates them:
unifi-family review "Kids iPad"
unifi-family review "Kids iPad" --all   # include every zone pair

# Preview a payload without sending:
unifi-family block "Kids iPad" --domain tiktok.com --dry-run

# Manage existing rules:
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
- optional daily **schedule** via `--start/--stop`

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
> combine with MDM/Screen Time for airtight control.
