import requests
import json
import re
import subprocess
import keyring
import argparse
from wattle import Wattle

__author__ = 'Russ Webber'

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
        self.courseid = courseid
        self.course_data = self.req_class()

        self.course_name = self.course_data['section']['course']['name'].replace('/', '-')

    def fixjson(self, broken):
        # the JSON returns a function call for some reason, this strips off the code and just parses the JSON
        broken = broken.replace('EC.loadRecordsSuccess(', '')
        broken = broken.replace('EC.loadDetailsSuccess(', '')
        return json.loads(broken[:-2])

    def req_class(self, number_of_lecs=50):
        r = self.wattle.sess.get(CLASS_DATA.format(self.courseid, number_of_lecs))
        return self.fixjson(r.text)

    def req_lec(self, puid):
        r = self.wattle.sess.get(LECTURE_DATA.format(self.courseid, puid))
        return self.fixjson(r.text)

    def download_lecture(self, uuid):
        lecdata = self.req_lec(uuid)

        week = int(lecdata['presentation']['week'])
        if week > 7:
            week -= 2  # remove the two week break from the number

        letter = re.search("Lecture (.)\\]$", lecdata['presentation']['title']).groups()[0]
        output = "{} - Week {} {}.m4v".format(self.course_name,
                                              week,
                                              letter)

        print("\nDownloading {} --> {}...".format(lecdata['presentation']['title'], output))
        subprocess.run(
            """curl -C - --retry 5 --referer "https://capture.anu.edu.au/ess/echo/presentation/{}/media.m4v?downloadOnly=true" --cookie "{}" --output "{}" {}""".format(
                lecdata['presentation']['uuid'],
                cookies_,
                output,
                lecdata['presentation']['vodcast'].replace('media', 'mediacontent')
            ), shell=True)

    def download_all_lectures(self):
        for lec in self.course_datae['section']['presentations']['pageContents']:
            self.download_lecture(lec['uuid'])



w = Wattle("u5451339", keyring.get_password('anu', 'u5451339'))
ed = Echo(w, courseid)

#print(course['section']['course']['name'], course['section']['presentations']['totalResults'])

