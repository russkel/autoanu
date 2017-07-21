import re
import logging
import argparse
import wattle
import keyring
import os
import time

# TODO python-dateutil has fuzzy date parsing for tutorial times
# TODO use fuzzywuzzy for fuzzy string matching of tutorial names
# TODO scheduling using sched


def group_signup_by_ident(watt, signupid, identifier):
    for group in watt.group_details(signupid=signupid):
        ident, description, capacity, post_data, signed_up = group

        if ident == identifier:
            logging.info("Found tutorial slot with ident {} and capacity {}".format(ident, capacity))
            if signed_up:
                # TODO detect signed-up if the leave group button isn't there
                logging.info("Already signed up for group for group id {}".format(signupid))
                return True

            if post_data:
                watt.group_send_postdata(signupid, post_data)
                return True
            else:
                logging.info("No sign up button for {}".format(ident))

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
                watt.group_send_postdata(signupid, post_data)

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


def leave(watt, signupid, group_details):
    for group in group_details:
        ident, description, capacity, post_data, signed_up = group

        if signed_up:
            logging.info("Going to leave tutorial slot with ident {} and capacity {}".format(ident, capacity))
            if signed_up:
                logging.info("Leaving {}".format(ident))

                if post_data:
                    watt.group_send_postdata(signupid, post_data)
                    return False
                else:
                    logging.info("No sign up button for {}".format(ident))
                    return False

    return True


def watch(watt, signupid, identifier):
    group_details = watt.group_details(signupid=signupid)
    for group in group_details:
        ident, description, capacity, post_data, signed_up = group
        capacity = [int(x) for x in capacity.split("/")]

        if ident == identifier:
            logging.info("Found tutorial slot with ident \"{}\" and capacity {}/{}".format(
                ident, capacity[0], capacity[1]))
            if signed_up:
                logging.info("Already signed up for group for group id {}".format(signupid))
                return True

            if capacity[0] < capacity[1]:
                # leave current group and join it
                logging.info("Leaving current group if required...")
                if leave(watt, signupid, group_details):
                    if post_data:
                        watt.group_send_postdata(signupid, post_data)
                        logging.info("Joined group!")
                        return True
                    else:
                        logging.info("No sign up button for {}".format(ident))
                else:
                    return group_signup_by_ident(watt, signupid, ident)


logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description='Automatically signs up to groups on Wattle')
parser.add_argument('--groupid', type=int, help='Specify the group ID to sign up for')
parser.add_argument('--id', help='The tutorial slot to sign up for (the string identifier from the group select page')
parser.add_argument('--watch', action='store_true', help='Watch a slot to free up.')
parser.add_argument('-u', '--username', help='Wattle username to log in with')

args = parser.parse_args()

if not args.username:
    if 'WATTLE_USERNAME' not in os.environ:
        parser.error("No Wattle username was provided, can't log in!")
    else:
        args.username = os.environ['WATTLE_USERNAME']

w = wattle.Wattle(args.username, keyring.get_password('anu', args.username))

if args.id and args.groupid:
    if args.watch:
        while True:
            if watch(w, args.groupid, args.id):
                break
            else:
                time.sleep(30)
    else:
        auto_signup(w, args.groupid, args.id)
