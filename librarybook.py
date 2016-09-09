import logging
import re
import datetime
import intervaltree
import requests
import lxml.html
import lxml.html.clean
import dateutil.parser
from collections import namedtuple

SITE = "https://library-admin.anu.edu.au/book-a-library-group-study-room/"
ACTION = SITE + "index.html"
RE_UNAVAIL = re.compile("Not available: (\\d+:\\d+) - (\\d+:\\d+)")
ROOM_SEATS = re.compile("Seats (\\d+)")
Room = namedtuple('Room', ['library', 'room_no', 'name', 'seats', 'description', 'available'])

# NOTE: Can book 10 days in advance, i.e. on the 7th you can book the 17th.


def time_string(s):
    hour, minute = [int(i) for i in s.split(":")]
    return datetime.time(hour, minute)


def time_to_interval(start, end):
    return start.hour + (start.minute/60), end.hour + (end.minute/60)


def parse_booking_dt(raw_dt):
    # parses datetimes in this format: Wednesday, 27 July 2016: 23:00 - 23:15
    raw_dt = raw_dt.split(':', 1)
    d = dateutil.parser.parse(raw_dt[0])

    start, finish = [dateutil.parser.parse(r) for r in raw_dt[1].split('-')]
    duration = finish - start
    dt = datetime.datetime.combine(d, start.time())

    return dt, duration


class LibraryBooking:
    def __init__(self, username, password):
        self.sess = requests.session()
        self.cleaner = lxml.html.clean.Cleaner(forms=False)

        logging.info("Logging into Library Booking Page with {}".format(username))
        self.homepage = self.sess.post(ACTION, {'inp_uid': username, 'inp_passwd': password})

        tree = lxml.html.fromstring(self.homepage.text)
        if not tree.xpath("//input[@id='logout']"):
            raise RuntimeError("Could not log in")

    def available_dates(self):
        tree = lxml.html.fromstring(self.homepage.text)

        for day in tree.xpath("//select[@name='bday']/option"):
            yield datetime.datetime.strptime(day.attrib['value'], "%Y-%m-%d").date()

    def available_libraries(self):
        tree = lxml.html.fromstring(self.homepage.text)
        return [(lib.attrib['value'], lib.text.strip())
                for lib in tree.xpath("//select[@name='building']/option") if lib.attrib['value']]

    def room_times(self, library, date):
        if type(date) == datetime.datetime:
            date = date.date()

        logging.info("Requesting booking times for {} on {}".format(library, date.isoformat()))
        html = self.sess.post(ACTION, {"ajax": "1", "building": library, "bday": date.isoformat(),
                                       "showBookingsForSelectedBuilding": "1"})

        tree = lxml.html.fromstring(html.text)

        hours = tree.xpath("//select[@id='bhour']/option")
        minutes = tree.xpath("//select[@id='bminute']/option")

        if tree.xpath("//form[@id='bform']") and not hours and not minutes:
            # library is closed
            return []

        earliest = datetime.time(int(hours[0].attrib['value']), int(minutes[0].attrib['value']))
        latest = datetime.time(int(hours[-1].attrib['value']), int(minutes[-1].attrib['value']))

        for room in tree.xpath("//input[@name='room_no']"):
            room_id = room.attrib['value']
            name = room.getnext()[0].text
            room_desc = room.getnext()[2].text
            available = intervaltree.IntervalTree.from_tuples([time_to_interval(earliest, latest)])

            seats = ROOM_SEATS.search(room_desc)
            room_seats = int(seats.groups()[0]) if seats else -1

            unavail = [RE_UNAVAIL.search(unav.text) for unav in room.getnext().getnext()]
            for start, finish in [match.groups() for match in unavail if match]:
                available.chop(*time_to_interval(time_string(start), time_string(finish)))

            yield Room(library, room_id, name, room_seats, room_desc, available)

    def make_booking(self, library_id, room_id, date_time, duration):
        logging.info('Sending booking request for {}:{} @ {} [{}]'.format(library_id, room_id, date_time, duration))
        html = self.sess.get(ACTION, params={
            "submitBooking": 1, "building": "{} Library".format(library_id), "room_no": room_id,
            "bday": date_time.date().isoformat(), "bhour": date_time.hour, "bminute": date_time.minute,
            "bookingPeriod": duration
        })

        tree = lxml.html.fromstring(html.text)
        table = tree.xpath("//div[@id='bookingresponse']/table/tr/td")

        if not table:
            error_msg = tree.xpath("//div[@id='bookingresponse']/div[@class='msg-error marginbottom']")
            if error_msg:
                raise RuntimeError("Booking failed: \"{}\"".format(error_msg[0].text))
            else:
                with open("error.txt", "wb") as f:
                    f.write(html.text.encode('utf-8'))
                raise RuntimeError("Unexpected error occurred. Cannot find booking confirmation table! Response saved to error.txt")

        booking_id = int(table[4].text)
        return booking_id

    def my_bookings(self):
        logging.info("Requesting bookings page")
        html = self.sess.post(ACTION, {"ajax": "1", "showMyBookings": "1"})
        tree = lxml.html.fromstring(self.cleaner.clean_html(html.text))

        table = tree.xpath("//table[@id='btable']")
        if not table:
            raise RuntimeError("Cannot find bookings table!")

        for row in table[0].xpath("./tr[td]"):
            room_no = row[0].text
            library = row[1].text
            dt, duration = parse_booking_dt(row[2].text)
            booking_id = int(row[3].xpath("./div/form/input[@name='booking_no']")[0].attrib['value'])

            yield booking_id, library, room_no, dt, duration


    #def delete_booking(self, booking_id):
    #TODO


if __name__ == "__main__":
    import argparse
    import tabulate
    import keyring
    import math
    import functools
    import os

    def draw(itree, start, end):
        columns = []
        for hr in range(math.floor(start), math.floor(end)):
            columns.append("".join("·" if itree[hr + minute] else "⁕" for minute in [0, .25, .5, .75]))

        return columns

    parser = argparse.ArgumentParser(description='Books library rooms at the ANU libraries')
    parser.add_argument('-u', '--username', help='Wattle username to log in with')
    parser.add_argument('--libraries', action='store_true', help='List libraries available')
    parser.add_argument('--dates', action='store_true', help='List dates that can be booked on')
    parser.add_argument('--bookings', action='store_true', help='List your bookings.')
    parser.add_argument('-D', '--datetime', type=functools.partial(dateutil.parser.parse, dayfirst=True),
                        help='Specify the date and time for the booking, such as -D "2016-07-26:14:00')
    parser.add_argument('-L', '--library', action='append', help='Specify the id of the library that the room is in')
    parser.add_argument('-R', '--room', action='append', help='Specify the priority list of room[s] to try and book')
    parser.add_argument('-T', '--duration', type=int, default=60,
                        help='Specify the duration of the booking, in increments of 15 mins, up to a maximum of '
                             '120 mins. Default is 60 mins.')
    parser.add_argument('--rooms', action='store_true', help='List rooms available for a library. Defaults to today.')
    parser.add_argument('--start', type=int, default=7, help='Show rooms from this hour. Defaults to 7:00')
    parser.add_argument('--end', type=int, default=20, help='Show rooms to this hour. Defaults to 20:00')
    parser.add_argument('--free', action='store_true', help='Only list rooms that are free at the datetime provided.')

    args = parser.parse_args()

    if not args.username:
        if 'WATTLE_USERNAME' not in os.environ:
            parser.error("No Wattle username was provided, can't log in!")
        else:
            args.username = os.environ['WATTLE_USERNAME']

    # TODO verbose option
    logging.basicConfig(level=logging.INFO)

    lb = LibraryBooking(args.username, keyring.get_password('anu', args.username))

    # TODO output ics file
    # TODO CalDAV Support (ties in with Google cal etc)
    # TODO fix extreme-end edge case

    if args.libraries:
        print(tabulate.tabulate([list(x) for x in lb.available_libraries()],
                                ['id', 'Library Name'], tablefmt="fancy_grid"))

    if args.dates:
        print("Dates that can be booked:")
        for d in lb.available_dates():
            print(' * ', d)

    if args.bookings:
        print(tabulate.tabulate([list(x) for x in lb.my_bookings()],
                                ['id', 'Library', 'Room', 'Booking Time', 'Duration'], tablefmt="fancy_grid"))

    if args.library:
        lib_ids = [l[0] for l in lb.available_libraries()]
        if not all(l in lib_ids for l in args.library):
            raise parser.error("Incorrect Library ID provided. It must consist of {}".format(
                ", ".join(lib_ids)
            ))

    if args.datetime:
        valid_dates = list(lb.available_dates())
        desired = args.datetime if type(args.datetime) is datetime.date else args.datetime.date()
        if desired not in valid_dates:
            raise parser.error("Cannot book on the date provided: {}".format(d))
    else:
        args.datetime = datetime.datetime.now()
        args.start = args.datetime.hour
        args.end = math.ceil(args.datetime.hour + 2*args.duration/60)

    if args.free and not type(args.datetime) == datetime.datetime:
        raise parser.error("Cannot show only free rooms without a time.")

    if args.rooms:
        if not args.library:
            args.library = [l[0] for l in lb.available_libraries()]
            rooms = []

            for library in args.library:
                for room in lb.room_times(library, args.datetime):
                    if args.free:
                        free_start = args.datetime.hour + args.datetime.minute / 60
                        free_end = free_start + args.duration / 60

                        if not any(x.contains_interval(intervaltree.Interval(free_start, free_end))
                                   for x in room.available[free_start:free_end]):
                            continue

                    rooms.append(room)

            hours = ["{:02}00".format(i) for i in range(args.start, args.end)]
            data = [[room.library, room.room_no, room.seats] + draw(room.available, args.start, args.end) + []
                    for room in rooms]
            print(tabulate.tabulate(data, ['Library', 'Room Id', 'Seats'] + hours + ['Description'],
                                    tablefmt="fancy_grid"))

        exit(0)

    if args.datetime and args.room and args.library:
        for library, room_id in zip(args.library, args.room):
            if type(args.datetime) is not datetime.datetime:
                raise parser.error("Cannot make a booking with just a date.")

            booking_id = lb.make_booking(library, room_id, args.datetime, args.duration)
            print("Booking successful. Booking Id: {}".format(booking_id))