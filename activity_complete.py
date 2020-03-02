# this python script will find closed stories in jira and synch back a checkmark to primavera
import main as m
import shlog
import configparser
from jiracmd import Jira
import requests


def post_act_complete(server, user, pw, ObjectId, complete=True):
    if complete:
        stat = "Completed"
    else:
        stat = "In Progress"
    request_data = {'Activity': {'ObjectId': ObjectId,
                                 'Status': stat}}
    synched = m.soap_request(request_data, server, 'ActivityService', 'UpdateActivities', user, pw)
    return synched


# read config and get primavera login info
parser = configparser.ConfigParser()
with open('login') as configfile:
    parser.read_file(configfile)
primadict=parser['primavera-section']
primauser=primadict['user']
primapasswd=primadict['passwd']
primaserver=primadict['server']
# read tool config
tool_dict = parser['tool-settings']
tool_log = tool_dict['loglevel']
loglevel=shlog.__dict__[tool_log]
assert type(loglevel) == type(1)
shlog.basicConfig(level=shlog.__dict__[tool_log])
shlog.verbose('Primavera connection will use:\nServer: ' + primaserver +
              '\nUser: ' + primauser + '\nPass: ' + '*'*len(primapasswd))
# init jira stuff
jcon = Jira('jira-section')

m.vpn_toggle(True)
act_tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, jcon.server)

# loop through act -> ticket records
for act in act_tickets:
    closed = jcon.check_if_closed(jcon.project, act_tickets[act])
    shlog.normal('Activity ID ' + str(act) + ' closed = ' + str(closed))
    reopened = jcon.check_if_reopened(jcon.project, act_tickets[act])
    shlog.normal('Activity ID ' + str(act) + ' (re)open = ' + str(reopened))
    info = m.get_act_info(act, primaserver, primauser, primapasswd)
    if closed:
        shlog.normal('\nREPORTED AS CLOSED\nAct Object ID: ' + str(act) +
                     '\nID: ' + info['Id'] +
                     '\nActivity Name: ' + info['Name'])
        shlog.verbose('JIRA Story: ' + act_tickets[act])
        resp = post_act_complete(primaserver, primauser, primapasswd, act)
    if reopened:
        shlog.normal('\nREPORTED AS (RE)OPEN\nAct Object ID: ' + str(act) +
                     '\nID: ' + info['Id'] +
                     '\nActivity Name: ' + info['Name'])
        shlog.verbose('JIRA Story: ' + act_tickets[act])
        resp = post_act_complete(primaserver, primauser, primapasswd, act, False)

m.vpn_toggle(False)
# TODO: add epic completion > activity completion check
# it's called status > finished
# TODO: mark imported stuff with yellow