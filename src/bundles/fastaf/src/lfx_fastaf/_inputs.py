"""Fresh native Langflow input definitions shared by the ten components."""

from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput


def api_key_input():
    return SecretStrInput(
        name="fastaf_api_key",
        display_name="FastAF API Key",
        required=True,
        password=True,
        info="Create an API key at https://fastaf.co/dashboard/. Calls consume FastAF credits; avoid blind retries.",
    )


def text_input(name, label, info, *, required=False, advanced=False, tool_mode=False, value=""):
    return MessageTextInput(
        name=name,
        display_name=label,
        info=info,
        required=required,
        advanced=advanced,
        tool_mode=tool_mode,
        value=value,
    )


def choice_input(name, label, options, value, info, *, advanced=False, tool_mode=False):
    return DropdownInput(
        name=name,
        display_name=label,
        options=options,
        value=value,
        info=info,
        advanced=advanced,
        tool_mode=tool_mode,
    )


def optional_bool(name, label, info):
    return choice_input(name, label, ["Default", "true", "false"], "Default", info, advanced=True)


def optional_int(name, label, info):
    # Native IntInput coerces None/blank to 0, which changes site defaults (wait)
    # or creates invalid dimensions. Blank text preserves omission; code validates.
    return text_input(name, label, f"{info} Integer; leave blank for the API default.", advanced=True)


def url_input():
    return text_input(
        "url",
        "Page URL",
        "Public HTTP(S) URL. Private targets and login paths are refused by FastAF.",
        required=True,
        tool_mode=True,
    )


def query_input(*, required=True):
    return text_input("query", "Search Query", "Search text for one results page.", required=required, tool_mode=True)


def localization_inputs():
    return [
        text_input("country", "Search Country", "Country code such as us or fr; no country surcharge.", advanced=True),
        text_input(
            "language", "Language", "Language code, such as en. Jobs uses locales such as en_us.", advanced=True
        ),
    ]


def search_page_inputs():
    return [
        optional_int("results", "Maximum Results", "1-100; limits this page, not additional pages."),
        optional_int("page", "Page", "Zero-based; 0 is the first paid page."),
        *localization_inputs(),
    ]


def scrape_inputs():
    return [
        url_input(),
        optional_bool("dynamic", "Render JavaScript", "Default preserves site rules, including Booking rendering."),
        optional_bool("premium", "Premium Proxies", "10 base credits; 25 with rendering."),
        text_input("proxy_country", "Proxy Country", "ISO country code; enables premium-tier pricing.", advanced=True),
        optional_int("wait", "Browser Wait (ms)", "0-35000; does not enable rendering. Blank preserves site defaults."),
        optional_bool(
            "challenge_mode", "Challenge Mode", "10 base credits; incompatible with rendering/premium/country."
        ),
    ]
