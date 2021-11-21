#!/usr/bin/env python3.9
import caldav
import requests
import tempfile
import camelot
from datetime import datetime
import logging
import re
from typing import Tuple, List, Union

SKATE_SCHEDULE_URL = "http://web.mit.edu/athletics/www/skateschedule.pdf"


def calendar_test():
    caldav_url = "http://localhost:8000/"
    calendar_url = "http://localhost:8000/user1/c3499118-8178-e872-7330-0847cb7824a2/"
    username = "user1"
    password = "foobar"

    client = caldav.DAVClient(url=caldav_url, username=username, password=password)

    mycal = caldav.Calendar(client=client, url=calendar_url)
    my_principal = client.principal()

    calendars = my_principal.calendars()

    if calendars:
        ## Some calendar servers will include all calendars you have
        ## access to in this list, and not only the calendars owned by
        ## this principal.
        print("your principal has %i calendars:" % len(calendars))
        for c in calendars:
            print("    Name: %-20s  URL: %s" % (c.name, c.url))
    else:
        print("your principal has no calendars")
        exit()

    ## Let's add an event to our newly created calendar
    mycal.save_event(
        """BEGIN:VCALENDAR
    VERSION:2.0
    PRODID:-//Example Corp.//CalDAV Client//EN
    BEGIN:VEVENT
    UID:foobar
    DTSTAMP:20200516T060000Z
    DTSTART:20200517T060000Z
    DTEND:20200517T230000Z
    RRULE:FREQ=YEARLY
    SUMMARY:Do the needful
    END:VEVENT
    END:VCALENDAR
    """
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

def pdf_test2():
    r = requests.get(SKATE_SCHEDULE_URL, stream=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        print(len(r.content))
        f.write(r.content)
        filename = f.name
    print(filename)
    tables = camelot.read_pdf(filename)[0].data[1:]
    # Flatten and don't include empty strings
    day_strs = [cell for row in tables for cell in row if len(cell) > 0]
    month = None
    for day_str in day_strs:
        try:
            day_split = day_str.split("\n")
            day = day_split[0].split()
            # Take month out of day if necessary
            if len(day) > 1:
                month = MONTH_MAP.get(day[-2].lower(), month)
            if month == None:
                raise ValueError("Unknown month")
            day = int(day[-1][:2])
            now = datetime.now().replace(month=month, day=day, second=0, microsecond=0)
            formatted = now.strftime("%Y%m%dT%H%M%SZ")
            print(repr(day_split))
            print(f"{day_str} -> {now}")
            event_name = None
            for line in day_split[1:]:
                cleaned = line.replace("–", "-").strip()
                if "-" in cleaned and event_name:
                    # Common typeos
                    cleaned = cleaned.lower()
                    print(
                        f"{repr(event_name.strip())}: {parse_time_range(now, cleaned)}"
                    )
                else:
                    event_name = cleaned
        except Exception as e:
            logging.exception(f"Failed to parse {repr(day_str)} with exception {e}")

def events_from_cell(cell: str, month: Union[int, None]) -> Tuple[List[Tuple[str, datetime, datetime]], Union[int, None]]:
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
    now = datetime.now().replace(month=month, day=day, second=0, microsecond=0)

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
    # TODO: publish_events(all_events)
    print(all_events)

if __name__ == "__main__":
    # calendar_test()
    # pdf_test2()
    main()
