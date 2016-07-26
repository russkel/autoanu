import logging
import re
import datetime
import intervaltree
import requests
import lxml.html

SITE = "https://library-admin.anu.edu.au/book-a-library-group-study-room/"
ACTION = SITE + "index.html"
RE_UNAVAIL = re.compile("Not available: (\\d+:\\d+) - (\\d+:\\d+)")


def time_string(s):
    hour, minute = [int(i) for i in s.split(":")]
    return datetime.time(hour, minute)


def time_to_interval(start, end):
    return start.hour + (start.minute/60), end.hour + (end.minute/60)


class LibraryBooking:
    def __init__(self, username, password):
        self.sess = requests.session()

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
        html = self.sess.post(ACTION, {"ajax": "1", "building": library, "bday": date.isoformat(),
                                       "showBookingsForSelectedBuilding": "1"})

        tree = lxml.html.fromstring(html.text)

        hours = tree.xpath("//select[@id='bhour']/option")
        minutes = tree.xpath("//select[@id='bminute']/option")
        earliest = datetime.time(int(hours[0].attrib['value']), int(minutes[0].attrib['value']))
        latest = datetime.time(int(hours[-1].attrib['value']), int(minutes[-1].attrib['value']))

        for room in tree.xpath("//input[@name='room_no']"):
            room_id = room.attrib['value']
            room_name = room.getnext()[0].text
            room_desc = room.getnext()[2].text
            available = intervaltree.IntervalTree.from_tuples([time_to_interval(earliest, latest)])

            unavail = [RE_UNAVAIL.search(unav.text) for unav in room.getnext().getnext()]
            for start, finish in [match.groups() for match in unavail if match]:
                available.chop(*time_to_interval(time_string(start), time_string(finish)))

            yield (room_id, room_name, room_desc), available

    def make_booking(self, library_id, room_id, date_time, duration):
        return False


if __name__ == "__main__":
    import argparse
    import tabulate
    import keyring
    import dateutil.parser

    parser = argparse.ArgumentParser(description='Books library rooms at the ANU libraries')
    parser.add_argument('--libraries', action='store_true', help='List libraries available')
    parser.add_argument('--dates', action='store_true', help='List dates that can be booked on')
    parser.add_argument('--username', help='Wattle username to log in with', required=True)
    parser.add_argument('-L', '--library', action='append', help='Specify the id of the library that the room is in')
    parser.add_argument('-D', '--datetime', action='append', type=dateutil.parser.parse,
                        help='Specify the date and time for the booking, such as -D "2016-07-26:14:00')
    parser.add_argument('-T', '--duration', action='append', type=int, default=60,
                        help='Specify the duration of the booking, in increments of 15 mins, up to a maximum of '
                             '120 mins. Default is 60 mins.')
    parser.add_argument('--rooms', action='store_true', help='List rooms available for a library. Defaults to today.')
    parser.add_argument('--free', action='store_true', help='Only list rooms that are free.') #TODO

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    lb = LibraryBooking(args.username, keyring.get_password('anu', args.username))

    # TODO if library specified, check it's valid
    # TODO if date specified, check can book on that date

    if args.libraries:
        print(tabulate.tabulate([list(x) for x in lb.available_libraries()],
                                ['id', 'Library Name'], tablefmt="fancy_grid"))

    if args.dates:
        print("Dates that can be booked:")
        for d in lb.available_dates():
            print(' * ', d)

    if args.rooms:
        if not args.library:
            raise argparse.ArgumentError("Need to specify a library to view the rooms of.")

        dates = args.datetime if args.datetime else [datetime.date.today()]
        for date in dates:
            if type(date) == datetime.datetime:
                date = date.date()

            for room, itree in lb.room_times(args.library, date):
                print(room, itree)

        # list free rooms on date time

    # TODO list own bookings

    from pprint import pprint
