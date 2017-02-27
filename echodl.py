import datetime
import os
import re
import subprocess

from wattle import Wattle
import dateutil.parser

#TODO add ffmpeg component to normalise and compress audio OR use Dynamic Audio Normalizer filter
#ffmpeg -i MATH1013\ -\ Week\ 1\ A.m4v -vcodec copy -ab 32 -af "dynaudnorm" MATH1013\ -\ Week\ 1\ Anorm.m4v
#strip the bloody copyright notice, 13secs in # -ss 13s
#fix metadata title of lecture video to include week

SITE = "https://capture.anu.edu.au:8443/ess/client/api/sections"
CLASS_DATA = SITE + "/{}/section-data.json?timeZone=Australia/Sydney&pageIndex=1&pageSize={}&sortOrder=desc&showUnavailable=true&timeZone=Australia/Sydney&callback=EC.loadRecordsSuccess"
LECTURE_DATA = SITE + "/{}/presentations/{}/details.json?timeZone=Australia/Sydney&isFaculty=false&callback=EC.loadDetailsSuccess"


class Echo:
    def __init__(self, wattle, courseid):
        self.wattle = wattle
        self.echoid = self.wattle.course_echo_session(courseid)

        if self.echoid:
            self.courseid = courseid
            self.course_data = self._req_class()
            self.course_name = self.course_data['section']['course']['name'].replace('/', '-')

    def _fix_json(self, broken):
        # the JSON returns a function call for some reason, this strips off the code and just parses the JSON
        broken = broken.replace('EC.loadRecordsSuccess(', '')
        broken = broken.replace('EC.loadDetailsSuccess(', '')
        return json.loads(broken[:-2])

    def _req_class(self, number_of_lecs=50):
        r = self.wattle.sess.get(CLASS_DATA.format(self.echoid, number_of_lecs))
        return self._fix_json(r.text)

    def lectures(self):
        if not self.echoid:
            return []

        for lec in self.course_data['section']['presentations']['pageContents']:
            yield lec['uuid'], lec['title']

    def req_lec(self, puid):
        r = self.wattle.sess.get(LECTURE_DATA.format(self.echoid, puid))
        return self._fix_json(r.text)

    def download_lecture(self, uuid, directory):
        lec_data = self.req_lec(uuid)

        week = int(lec_data['presentation']['week'])
        if week > 7:
            week -= 2  # remove the two week break from the number

        letter = re.search("Lecture (.)\\]$", lec_data['presentation']['title'])
        if letter:
            letter = letter.groups()[0]
            filename = "{} - Week {:02} {}.m4v".format(self.course_name, week, letter)
        else:
            date = dateutil.parser.parse(lec_data['presentation']['startTime'])
            filename = "{} - Week {:02} {}.m4v".format(self.course_name, week, date.strftime('%Y-%M-%d %a %H%M'))

        print("\nDownloading {} --> {}...".format(lec_data['presentation']['title'], filename))
        error_code = self.download(uuid, lec_data['presentation']['vodcast'].replace('media', 'mediacontent'),
                      os.path.join(directory, filename))
        return filename, error_code

    def download(self, uuid, media_url, file_path):
        proc = subprocess.run(
            """curl -C - --retry 5 --referer "https://capture.anu.edu.au/ess/echo/presentation/{}/media.m4v?downloadOnly=true" --cookie "{}" --create-dirs --output "{}" {}""".format(
                uuid, #lec_data['presentation']['uuid'],
                "; ".join("{}={}".format(x, y) for x, y in self.wattle.sess.cookies.iteritems()),
                file_path,
                media_url
            ), shell=True)

        return proc.returncode


if __name__ == "__main__":
    import json
    import logging
    import argparse

    import prompt_toolkit
    from tabulate import tabulate
    import keyring

    def notify(title, text):
        logging.info(text)
        os.system("""osascript -e 'display notification "{}" with title "{}"'""".format(text, title))

    subs_file = os.path.expanduser('~/.echodlsubs.json')
    echo_db_file = os.path.expanduser('~/.echodldb.json')
    download_dir = os.path.expanduser('~/EchoDL/')

    parser = argparse.ArgumentParser(description='Echo360 Downloader')
    parser.add_argument('-u', '--username', help='Wattle username to log in with')
    parser.add_argument('--subscriptions', action='store_true', help='[Re]Set subscriptions')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if not args.username:
        if 'WATTLE_USERNAME' not in os.environ:
            parser.error("No Wattle username was provided, can't log in!")
        else:
            args.username = os.environ['WATTLE_USERNAME']

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    w = Wattle(args.username, keyring.get_password('anu', args.username))

    if args.subscriptions or not os.path.exists(subs_file):
        courses = w.courses()
        navigate = [(i, c[1]) for i, c in enumerate(courses)]

        print(tabulate(navigate))
        subs = prompt_toolkit.prompt("Subscribe to? ")
        subs = [courses[int(s)] for s in subs.split()]

        with open(subs_file, "w") as file:
            json.dump({course_id: {'title': title} for course_id, title in subs}, file)

    with open(subs_file, "r") as file:
        subs_file_contents = json.load(file)

    if os.path.exists(echo_db_file):
        with open(echo_db_file, "r") as file:
            echo_db = json.load(file)
    else:
        echo_db = {}

    for course in subs_file_contents.keys():
        ed = Echo(w, course)

        if course not in echo_db:
            echo_db[course] = []

        for lecture_uuid, lecture_title in ed.lectures():
            if lecture_uuid not in echo_db[course]:
                notify("EchoDL", "Downloading {}...".format(lecture_title))
                filename, error_code = ed.download_lecture(lecture_uuid, download_dir)

                if error_code == 0:
                    echo_db[course].append(lecture_uuid)
                    notify("EchoDL", "Downloaded {}.".format(filename))
                else:
                    notify("EchoDL", "Error occurred!")

    with open(echo_db_file, "w") as file:
        json.dump(echo_db, file)
