import requests
import lxml.html
import logging
import re
import keyring
import datetime
import argparse
from urllib.parse import urlparse

SITE = "http://library-admin.anu.edu.au/book-a-library-group-study-room/"
ACTION = SITE + "index.html"
RE_UNAVAIL = re.compile("Not available: (\\d+:\\d+) - (\\d+:\\d+)")

from pprint import pprint

logging.basicConfig(level=logging.INFO)


def time_string(s):
    hour, minute = [int(i) for i in s.split(":")]
    return datetime.time(hour, minute)


class LibraryBooking:
    def __init__(self, username, password):
        self.sess = requests.session()

        logging.info("Logging into Library Booking Page with {}".format(username))
        self.homepage = self.sess.post(ACTION, {'inp_uid': username, 'inp_passwd': password})

    def available_dates(self):
        tree = lxml.html.fromstring(self.homepage.text)

        for day in tree.xpath("//select[@name='bday']/option"):
            yield datetime.datetime.strptime(day.attrib['value'], "%Y-%m-%d").date()

    def available_libraries(self):
        tree = lxml.html.fromstring(self.homepage.text)
        return [lib.attrib['value'] for lib in tree.xpath("//select[@name='building']/option") if lib.attrib['value']]

    def room_times(self, library, date):
        html = self.sess.post(ACTION, {"ajax": "1",
                                       "building": library,
                                       "bday": date.isoformat(),
                                       "showBookingsForSelectedBuilding": "1"})

        tree = lxml.html.fromstring(html.text)

        for room in tree.xpath("//input[@name='room_no']"):
            room_id = room.attrib['value']
            room_name = room.getnext()[0].text
            room_desc = room.getnext()[2].text

            unavail = [RE_UNAVAIL.search(unav.text).groups() for unav in room.getnext().getnext()]
            unavail = [(time_string(start), time_string(finish)) for start, finish in unavail]
            yield room_id, room_name, room_desc, unavail

# TODO argparse
# list libraries
# list dates
# list rooms on date
# list free rooms on date time
# list booking times on day for library
# set -- booking length

lb = LibraryBooking("u5451339", keyring.get_password('anu', 'u5451339'))
#pprint(list(lb.available_dates()))
#pprint(lb.available_libraries())
pprint(list(lb.room_times("Chifley", datetime.date(2016, 2, 23))))