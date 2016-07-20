import re
import logging
import argparse
import wattle
import keyring

# TODO python-dateutil has fuzzy date parsing for tutorial times
# TODO use fuzzywuzzy for fuzzy string matching of tutorial names
# TODO scheduling


def group_signup_by_ident(watt, signupid, identifier):
    for group in watt.group_details(signupid=signupid):
        ident, description, capacity, post_data, signed_up = group

        if ident == identifier:
            if signed_up:
                # TODO detect signed-up if the leave group button isn't there
                logging.info("Already signed up for group for group id {}".format(signupid))
                return True

            if post_data:
                watt.group_send_signup(signupid, post_data)

    return False


def group_fuzzy_signup(watt, signupid, name):
    for group in watt.group_details(signupid=signupid):
        ident, description, capacity, post_data, signed_up = group

        desc_match = [re.search(name, ident) for ident in description]
        if re.search(name, ident) or any(desc_match):
            if signed_up:
                logging.info("Already signed up for group for group id {}".format(signupid))
                return True

            if post_data:
                watt.group_send_signup(signupid, post_data)

    return False


def auto_signup(watt, signupid, ident):
    while True:
        if group_signup_by_ident(watt, signupid, ident):
            break


def auto_fuzzy_signup(watt, courseid, ident):
    signupid = None

    while not signupid:
        su = list(watt.course_signups(courseid))
        if su:
            signupid = su[0][0]

    while True:
        if group_fuzzy_signup(watt, signupid, ident):
            break

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description='Automatically signs up to groups on Wattle')
parser.add_argument('--groupid', type=int, help='Specify the group ID to sign up for')
parser.add_argument('--id', help='The tutorial slot to sign up for (the string identifier from the group select page')
parser.add_argument('--username', help='Wattle username to log in with', required=True)

args = parser.parse_args()

w = wattle.Wattle(args.username, keyring.get_password('anu', args.username))

if args.id and args.groupid:
    auto_signup(w, args.groupid, args.id)

#auto_fuzz_signup(17641, "Tutorial (?:Group )?0?5")

#pprint(list(w.group_details(902521)))
#(902521, 'Tutorial 06')