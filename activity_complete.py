# this python script will find closed stories in jira and synch back a checkmark to primavera
import main as m
import shlog
import configparser
from jiracmd import Jira
import requests


def post_act_complete(server, user, pw, ObjectId, status):
    # possible status values: "Completed", "In Progress", "Not Started"
    request_data = {'Activity': {'ObjectId': ObjectId,
                                 'Status': status}}
    shlog.normal('Making request to change status to ' + status)
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
    closed = jcon.check_if_complete(jcon.project, act_tickets[act])
    shlog.normal('Activity ID ' + str(act) + ' closed = ' + str(closed))

    inprogress = jcon.check_if_open(jcon.project, act_tickets[act])
    shlog.normal('Activity ID ' + str(act) + ' inprogress = ' + str(inprogress))

    unstarted = jcon.check_if_unstarted(jcon.project, act_tickets[act])
    shlog.normal('Activity ID ' + str(act) + ' unstarted = ' + str(inprogress))

    info = m.get_act_info(act, primaserver, primauser, primapasswd)
    if closed:
        shlog.normal('\nREPORTED AS CLOSED\nAct Object ID: ' + str(act) +
                     '\nID: ' + info['Id'] +
                     '\nActivity Name: ' + info['Name'])
        shlog.verbose('JIRA Story: ' + act_tickets[act])
        resp = post_act_complete(primaserver, primauser, primapasswd, act, 'Completed')

    if inprogress:
        shlog.normal('\nREPORTED AS INPROGRESS\nAct Object ID: ' + str(act) +
                     '\nID: ' + info['Id'] +
                     '\nActivity Name: ' + info['Name'])
        shlog.verbose('JIRA Story: ' + act_tickets[act])
        resp = post_act_complete(primaserver, primauser, primapasswd, act, 'In Progress')

    if unstarted:
        shlog.normal('\nREPORTED AS NOT STARTED\nAct Object ID: ' + str(act) +
                     '\nID: ' + info['Id'] +
                     '\nActivity Name: ' + info['Name'])
        shlog.verbose('JIRA Story: ' + act_tickets[act])
        resp = post_act_complete(primaserver, primauser, primapasswd, act, 'Not Started')

m.vpn_toggle(False)
# TODO: add epic completion > activity completion check
# it's called status > finished
# TODO: mark imported stuff with yellow