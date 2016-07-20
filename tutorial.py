import re
import logging
import wattle
import keyring

logging.basicConfig(level=logging.INFO)


# TODO python-dateutil has fuzzy date parsing for tutorial times
# TODO use fuzzywuzzy for fuzzy string matching of tutorial names
# TODO scheduling


def group_signup_by_ident(watt, signupid, identifier):
    for group in watt.group_details(signupid=signupid):
        ident, description, capacity, post_data, signed_up = group

        if ident == identifier:
            if signed_up:
                # TODO still sends sign up for courses where group leaving is disabled
                logging.info("Already signed up for group for group id {}".format(signupid))
                return True

            watt.group_send_signup(signupid, post_data)

    return False


def group_fuzzy_signup(watt, signupid, name):
    for group in watt.group_details(signupid=signupid):
        ident, description, capacity, post_data, signed_up = group

        desc_match = [re.search(name, ident) for ident in description]
        if re.search(name, ident) or any(desc_match):
            if signed_up:
                # TODO still sends sign up for courses where group leaving is disabled
                logging.info("Already signed up for group for group id {}".format(signupid))
                return True

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


from pprint import pprint

w = wattle.Wattle("u5451339", keyring.get_password('anu', 'u5451339'))
#pprint(w.courses())
#pprint(w.course_echo_session(14319))
#w.auto_signup(938775, '3. World Solar Car Competition (ANU)')
#w.auto_signup(938775, '3. World Solar Car Competition (ANU)')

#pprint(list(w.course_signups(17894)))

#auto_fuzz_signup(17641, "Tutorial (?:Group )?0?5")

#pprint(list(w.group_details(902521)))
#(902521, 'Tutorial 06')