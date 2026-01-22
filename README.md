# HA Electric Usage Downloader

The **HA Electric Usage Downloader** integration allows you to download and display your electric usage data from the BlueBonnet SmartHub portal directly in Home Assistant. This integration polls the SmartHub API every 15 minutes to provide real-time data about your electricity consumption.

## Features
- **Electric Usage Data**: Automatically fetches your electric usage from the BlueBonnet SmartHub portal every 15 minutes.
- **Configurable URLs**: Allows you to configure the login and usage URLs for flexibility with different SmartHub instances.
- **Easy Integration**: Once set up, your electric usage data is displayed as a sensor in Home Assistant.

## Requirements
- BlueBonnet SmartHub account credentials (username and password).
- Home Assistant (version 2023.1.0 or higher).

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

## Configuration Instructions

After installation, you can configure the integration through the Home Assistant UI.

1. Go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for `HA Electric Usage Downloader` and select it.
3. Enter your **username** and **password** for the BlueBonnet SmartHub portal.
4. Input the **login URL** and **usage URL** for your SmartHub provider.
- Default bluebonnet URLs: (Change config_flow.py URL for COOP that leads to SmartHub)
  - Login URL: `https://bluebonnet.smarthub.coop/Login.html`
  - Usage URL: `https://bluebonnet.smarthub.coop/Usage/Usage.htm`
5. Complete the configuration, and a new sensor entity will be created with your electric usage data.

---

## Usage

Once the integration is configured, you will have a sensor in Home Assistant that displays your current electric usage in kWh. This data will be updated every 15 minutes.

You can view this sensor in your Home Assistant dashboard or use it in automations, scripts, or notifications to track your energy consumption.

---

## Troubleshooting

If you encounter issues:
- **Verify URLs**: Ensure that you have entered the correct login and usage URLs for your provider.
- **Check Logs**: Look at the Home Assistant logs (under **Settings** > **System** > **Logs**) for any error messages related to the integration.
- **Authentication Errors**: If login fails, ensure your credentials are correct for the BlueBonnet SmartHub portal.

---

## Dependencies

This integration requires the following Python libraries:
- `beautifulsoup4`
- `aiohttp`

These are automatically installed when you install the integration.

---

## FAQ

**1. What if my SmartHub provider uses a different URL?**

You can enter the correct URLs for your provider during setup. The integration is flexible and works with any SmartHub instance that follows the same login and usage structure.

**2. How often does the integration fetch data?**

The integration fetches data every 15 minutes by default, but you can adjust this interval in the integration settings if needed.

---

## Support

For any issues or feature requests, please create an issue on the [GitHub repository](https://github.com/trooperthorn/ha-SmartHub_coop-electric-usage).
