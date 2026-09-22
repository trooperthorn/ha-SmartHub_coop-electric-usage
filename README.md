# SmartHub Co-op Electric Usage

A Home Assistant integration that imports hourly electric usage from a NISC SmartHub co-op portal (for example `bluebonnet.smarthub.coop`) into Home Assistant long-term statistics, so it appears in the Energy dashboard stamped with the hour the energy was actually used.

## How it works

SmartHub is a single-page web application backed by JSON services. This integration makes the same calls the portal's Usage Explorer makes:

1. `GET /ui/` to receive the portal's `XSRF-TOKEN` cookie.
2. `POST /services/oauth/auth/v2` with `userId` and `password` (form encoded) and the `X-XSRF-TOKEN` header. The response carries a bearer token and its expiry.
3. `GET /services/secured/accounts` to list account and service location numbers.
4. `POST /services/secured/utility-usage/poll` with the account, service location, time frame (`HOURLY`) and a millisecond epoch range. The server first answers `PENDING`; the client re-posts until it answers `COMPLETE`.

The token is kept in memory only and reused until shortly before it expires. A `401` triggers exactly one fresh login; a second rejection starts Home Assistant's reauthentication flow.

This exchange was observed against bluebonnet.smarthub.coop (portal version 26.16.0) in September 2026. It is not a published API, and a co-op or NISC can change it without notice.

### Net meters (solar)

A net meter reports three channels, identified by the meter's flow direction rather than by display name:

| Flow direction | Statistic | Notes |
|---|---|---|
| `FORWARD` | `...consumption` | Energy drawn from the grid |
| `REVERSE` | `...generation` | Energy sent to the grid, stored as a positive number (the portal charts it as negative) |
| `NET` | `...net` | Consumption minus generation; its running sum can go down |

A meter without solar reports only consumption.

## Requirements

- A SmartHub login without a second factor. Logins that require two-factor authentication are not supported.
- Home Assistant 2026.9.0 or newer, with the recorder enabled (it is by default).

---

## Installation Instructions

### Installation via HACS

To install this integration via HACS (Home Assistant Community Store), follow these steps:

1. Open **Home Assistant** and go to **HACS** > **Integrations**.
2. Click on the three-dot menu in the upper-right corner and select **Custom Repositories**.
3. In the repository URL field, add the following: [https://github.com/trooperthorn/ha-electric-usage-downloader](https://github.com/trooperthorn/ha-SmartHub_coop-electric-usage)
4. Set the **Category** to **Integration** and click **Add**.
5. After adding the repository, search for `HA Electric Usage Downloader` in the HACS Integrations tab.
6. Click **Install**.
7. Restart Home Assistant to apply the changes.

### Manual Installation

If you prefer to install the integration manually:

1. Download the latest version of the integration from the GitHub repository: [https://github.com/trooperthorn/ha-electric-usage-downloader](https://github.com/trooperthorn/ha-SmartHub_coop-electric-usage)
2. Copy the `ha_electric_usage_downloader` folder from `custom_components/` into your Home Assistant `custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

1. Go to **Settings > Devices & Services > Add Integration** and search for **SmartHub Co-op Electric Usage**.
2. Enter your co-op's portal host (a pasted URL such as `https://bluebonnet.smarthub.coop/ui/` is accepted), your username, and your password. The login is verified before the entry is created.
3. If the login has more than one service location, choose one. Add the integration again for each additional location.

### Energy dashboard

Under **Settings > Dashboards > Energy**, add the statistic named **SmartHub \<account\> consumption** as grid consumption and, for a net meter, **SmartHub \<account\> generation** as return to grid. Use the statistics, not the sensors.

## What gets created

| Item | Purpose |
|---|---|
| External statistics per channel | Hourly kWh with a running sum. This is the data the Energy dashboard uses. |
| Sensors: consumption, generation, net (last 24 hours of data) | Informational. They have no state class on purpose, so they never create a second energy statistic. |
| Sensor: latest reading (diagnostic) | When the portal last published a reading. Readings typically lag by hours to a day. |

## Polling and history

- The portal is polled every 2 hours. Readings are published late, so polling faster would add load without producing newer data.
- Every refresh re-imports the last 3 days, so late or revised readings replace earlier values. Sums are re-anchored on the last stored hour before that window, which keeps the series continuous.
- The first run imports the last 30 days. If Home Assistant was offline longer than 3 days, the window reaches back to the last imported hour.

## Upgrading from 2026.09.04.1 and earlier

Earlier versions scraped `/Login.html` and `/Usage/Usage.htm`. Existing entries are migrated automatically: the host is taken from the old login URL, and if the login has exactly one service location it is adopted. If it has several, the entry asks you to remove and re-add the integration so the correct meter is chosen. The old `Electric Usage` sensor is replaced.

## Security notes

- Credentials are stored in the Home Assistant config entry, as with other cloud integrations. The bearer token is never written to disk.
- Each entry uses its own HTTP session and cookie jar, so portal cookies do not reach other integrations.
- Diagnostics redact the username, password, account number and service location number.
- The integration sends a User-Agent that identifies it, rather than imitating a browser.

## Troubleshooting

- **Invalid authentication**: sign in on the portal website with the same credentials. If the website asks for a code, the login uses two-factor authentication and is not supported.
- **Cannot connect**: check the host name. Enable debug logging for `custom_components.ha_electric_usage_downloader` to see each request path and status (tokens and passwords are never logged).
- **No new data**: compare the **Latest reading** sensor with the portal. If the portal has not published newer readings, the integration cannot either.

## Support

Report issues on the [GitHub repository](https://github.com/trooperthorn/ha-SmartHub_coop-electric-usage/issues).
