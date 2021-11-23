#!/usr/bin/env python3.9
import logging
import os
import re
import tempfile
from datetime import datetime
from textwrap import dedent
from typing import List, Tuple, Union

import caldav
import camelot
import requests
from pytz import timezone

SKATE_SCHEDULE_URL = "http://web.mit.edu/athletics/www/skateschedule.pdf"
EST5EDT = timezone("EST5EDT")
CALDAV_URL = os.environ['CALDAV_URL']
CALENDAR_ID = os.environ['CALENDAR_ID']
CALDAV_USERNAME = os.environ['CALDAV_USERNAME']
CALDAV_PASSWORD = os.environ['CALDAV_PASSWORD']


def as_caldav_timestamp(time: datetime):
    return datetime.utcfromtimestamp(time.timestamp()).strftime("%Y%m%dT%H%M%SZ")


def publish_events(events):
    client = caldav.DAVClient(url=CALDAV_URL, username=CALDAV_USERNAME, password=CALDAV_PASSWORD)

    mycal = caldav.Calendar(client=client, url=f"{CALDAV_URL}/{CALDAV_USERNAME}/{CALENDAR_ID}/")

    ## Let's add an event to our newly created calendar
    for event in events:
        title = event[0]
        dtstart, dtend = [as_caldav_timestamp(time) for time in event[1:]]
        mycal.save_event(
            dedent(
                f"""
                BEGIN:VCALENDAR
                VERSION:2.0
                PRODID:-//MIT Skating Calendar//MIT Skating Calendar Client//EN
                BEGIN:VTIMEZONE
                TZID:US-Eastern
                BEGIN:STANDARD
                DTSTART:19671029T020000
                RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10
                TZOFFSETFROM:-0400
                TZOFFSETTO:-0500
                TZNAME:Eastern Standard Time (US &amp; Canada)
                END:STANDARD
                BEGIN:DAYLIGHT
                DTSTART:19870405T020000
                RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=4
                TZOFFSETFROM:-0500
                TZOFFSETTO:-0400
                TZNAME:Eastern Daylight Time (US &amp; Canada)
                END:DAYLIGHT
                END:VTIMEZONE
                BEGIN:VEVENT
                UID:{dtstart}-{dtend}-{title.replace(" ", "-")}
                TZID:US-Eastern
                TZNAME:Eastern Standard Time (US & Canada)
                DTSTAMP:{dtstart}
                DTSTART:{dtstart}
                DTEND:{dtend}
                SUMMARY:{title}
                DESCRIPTION:Skating! Automatically generated events based on http://web.mit.edu/athletics/www/skateschedule.pdf
                END:VEVENT
                END:VCALENDAR
                """
            )
        )

    print(mycal.name, mycal.url, mycal.events())


def is_pm(time_str: str, other_time_str: str) -> bool:
    """
    is_pm returns true if time_str is PM or if it's not AM and the other time
    string is PM

    Requires all strings to be lower
    """
    return "pm" in time_str or ("am" not in time_str and "pm" in other_time_str)


def parse_time(time_str: str, time_is_pm: bool) -> Tuple[int, int]:
    """
    Note: Doen't handle midnight, does handle noon
    """
    clean_time = re.sub(r"(a|p)m.*", "", time_str)
    ints = [int(val) for val in clean_time.split(":")]
    hour = ints[0]
    minute = 0 if len(ints) == 1 else ints[1]
    return hour + (12 if time_is_pm and hour < 12 else 0), minute


def parse_time_range(day: datetime, time_str: str) -> Tuple[datetime, datetime]:
    start_str, end_str = [time.lower().strip() for time in time_str.split("-")]

    start_is_pm = is_pm(start_str, end_str)
    end_is_pm = is_pm(end_str, start_str)

    start_h, start_m = parse_time(start_str, start_is_pm)
    end_h, end_m = parse_time(end_str, end_is_pm)

    return day.replace(hour=start_h, minute=start_m), day.replace(
        hour=end_h, minute=end_m
    )


MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def events_from_cell(
    cell: str, month: Union[int, None]
) -> Tuple[List[Tuple[str, datetime, datetime]], Union[int, None]]:
    # Split cell into lines
    cell_lines = cell.split("\n")

    # Get the first line in the cell
    # ([sometimes junk] [sometimes month] [day number])
    day_header = cell_lines[0].split()

    # Take month out of day_header if necessary
    if len(day_header) > 1:
        month = MONTH_MAP.get(day_header[-2].lower(), month)
    if month == None:
        raise ValueError("Unknown month")

    # Get the day number
    day = int(day_header[-1][:2])

    # Create a datetime with the current year
    now = datetime.now(EST5EDT).replace(month=month, day=day, second=0, microsecond=0)

    # Keep track of the event_name
    event_name = None
    events = []
    for line in cell_lines[1:]:
        # Fix issue with "minus sign" vs "hyphen"
        cleaned = line.replace("–", "-").strip()

        # Found a time range
        if "-" in cleaned and event_name:
            # Common typeos
            cleaned = cleaned.lower()
            events.append((event_name, *parse_time_range(now, cleaned)))
        else:
            event_name = cleaned
    return events, month


def fetch_table_data():
    r = requests.get(SKATE_SCHEDULE_URL, stream=True)

    # Save to a tempfile and read it into camelot
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(r.content)
        table = camelot.read_pdf(f.name)[0].data[1:]

    # Flatten and don't include empty strings
    return [cell for row in table for cell in row if len(cell) > 0]


def main():
    data = fetch_table_data()

    # Keep track of month to use as a default month if it stops being written
    month = None
    all_events = []
    for cell in data:
        try:
            events, month = events_from_cell(cell, month)
            all_events.extend(events)
        except Exception as e:
            logging.exception(f"Failed to parse {repr(cell)} with exception {e}")
    publish_events(all_events)


if __name__ == "__main__":
    main()
