"""Execute native Langflow components without running a server or LLM."""

from datetime import date, timedelta

from lfx_fxmacrodata import FXMacroDataQuery


def main() -> None:
    today = date.today()
    operations = [
        ("data_catalogue", {"currency": "USD"}),
        ("indicator_history", {
            "currency": "USD", "indicator": "inflation",
            "start_date": (today - timedelta(days=90)).isoformat(), "end_date": today.isoformat(),
        }),
        ("release_calendar", {
            "currency": "USD", "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
        }),
    ]
    for operation, arguments in operations:
        component = FXMacroDataQuery()
        component.set(operation=operation, arguments=arguments, api_key="", timeout=30)
        frame = component.build_table()
        print(f"{operation}: {len(frame)} DataFrame rows")
        print(frame.attrs["source_url"])
        print(frame.attrs["provider_url"])
        if frame.empty:
            print("No records available in this window.")


if __name__ == "__main__":
    main()
