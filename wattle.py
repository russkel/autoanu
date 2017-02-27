import requests
import lxml.html
import logging
import re
from urllib.parse import urlparse

SITE = "https://wattlecourses.anu.edu.au"
COURSE = SITE + "/course/view.php?id={}"
GROUP = SITE + "/mod/groupselect/view.php?id={}"
GROUP_VIEW = SITE + "/mod/groupselect/view.php"


class Wattle:
    def __init__(self, username, password):
        self.sess = requests.session()

        logging.info("Logging into WATTLE with {}".format(username))
        self.homepage = self.sess.post(SITE + "/login/index.php",
                                       {'username': username, 'password': password, 'rememberusername': 0})

    def courses(self):
        tree = lxml.html.fromstring(self.homepage.text)

        courses = tree.xpath("//div[@id='course_list']/div[@class='box coursebox']")
        out = []
        for c in courses:
            course_id = int(c.attrib['id'].replace('course-', ''))
            title = c.xpath("div[@class='course_title']/h3/a")[0].text.strip()
            out.append((course_id, title))

        return out

    def course_echo_session(self, courseid):
        logging.info("Getting ECHO360 landing page for course id {}".format(courseid))
        p = self.sess.get(COURSE.format(courseid))
        tree = lxml.html.fromstring(p.text)
        echoblockurl = tree.xpath("//div[@class='block_echo360_echocenter']/a")[0].attrib['href']

        p = self.sess.get(echoblockurl)
        tree = lxml.html.fromstring(p.text)
        echourl = tree.xpath("//iframe")[0].attrib['src']
        url = urlparse(echourl)
        logging.info("Sending ECHO360 login")
        p = self.sess.get(echourl)
        tree = lxml.html.fromstring(p.text)

        if "Missing course section" in p.text:
            return None

        echourl2 = tree.xpath("//iframe")[0].attrib['src']  # partial URL
        logging.info("Sending 2nd round ECHO360 login")
        p = self.sess.get(url.scheme + "://" + url.netloc + echourl2)

        echo_id = re.search("/section/(.*?)\\?api", echourl2).groups()[0]
        return echo_id

    def course_signups(self, courseid):
        p = self.sess.get(COURSE.format(courseid))
        tree = lxml.html.fromstring(p.text)

        sign_ups = tree.xpath('//li[contains(concat(" ", normalize-space(@class), " "), " groupselect ")]')

        for su in sign_ups:
            group_id = int(su.attrib['id'].replace('module-', ''))
            title = su.xpath('.//span[@class="instancename"]')[0].text
            yield group_id, title

    def group_details(self, signupid):
        logging.info("Getting group sign up details for id {}".format(signupid))
        p = self.sess.get(GROUP.format(signupid))
        tree = lxml.html.fromstring(p.text)

        #<div class="alert alert-error">Group selection will be available on Monday, 15 February 2016, 4:00 PM.</div>

        slots = []
        for row in tree.xpath("//table[@class='generaltable']/tbody/tr"):
            #<div class="maxlimitreached">Maximum number reached</div>

            identifier = row[0].xpath(".//text()")[0]
            description = [d.strip() for d in row[1].xpath(".//div/p/span/text()")]
            capacity = row[2].text
            post_data = None
            signed_up = False

            last_td = row[-1]
            signupvals = last_td.xpath(".//input") #div/form/div/
            if signupvals:
                post_data = dict((field.attrib['name'], field.value)
                                 for field in signupvals if 'name' in field.attrib)
                if "Leave group" in signupvals[0].value:
                    signed_up = True

            slots.append((identifier, description, capacity, post_data, signed_up))

        return slots

    def group_send_signup(self, signupid, post_data):
        logging.info("Sending group sign up for id {}".format(signupid))
        p = self.sess.post(GROUP_VIEW.format(signupid), post_data)
        tree = lxml.html.fromstring(p.text)

        signupvals = tree.xpath("//form[@class='mform']/div/input")
        if signupvals:
            post_data = dict((field.attrib['name'], field.value)
                             for field in signupvals if 'name' in field.attrib)
            logging.info("Sending group sign up confirmation".format(signupid))
            p = self.sess.post(GROUP_VIEW.format(signupid), post_data)
            return p
