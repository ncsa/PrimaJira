# diff tool to compare primavera vs jira
# all findings are provided with possible resolutions
import main as m
import shlog
import configparser
import jira_utils as ju
from jiracmd import Jira


# find steps with matching names, but no ticket
# WHEN AVAILABLE: check hours vs story points

# read config and get primavera login info
parser = configparser.ConfigParser()
with open('login') as configfile:
    parser.read_file(configfile)
primadict=parser['primavera-section']
primauser=primadict['user']
primapasswd=primadict['passwd']
primaserver=primadict['server']
# read jira info for verbose output
jiradict=parser['jira-section']
jiraproject = jiradict['project']
# read tool config
tool_dict = parser['tool-settings']
tool_log = tool_dict['loglevel']
loglevel=shlog.__dict__[tool_log]
assert type(loglevel) == type(1)
shlog.basicConfig(level=shlog.__dict__[tool_log])
shlog.verbose('Primavera connection will use:\nServer: ' + primaserver +
              '\nUser: ' + primauser + '\nPass: ' + '*'*len(primapasswd))# init jira connection
# init jira stuff
jcon = Jira('jira-section')
con = ju.get_con('jira-section')

shlog.verbose('Getting ticket IDs and activities due for export')
tickets = m.get_activity_tickets(primaserver, primauser, primapasswd)
step_tickets = m.get_step_tickets(primaserver, primauser, primapasswd)
synched = m.get_synched_activities(primaserver, primauser, primapasswd)
activities, steps = m.get_steps_activities(synched, primaserver, primauser, primapasswd)

# find activities not yet imported
shlog.normal('---CHECKING FOR ACTIVITIES NOT YET IMPORTED---')
for act in activities:
    if act not in tickets.keys():
        shlog.normal('Activity #' + str(act) + ' (' + activities[act]['Name'] + ')  is marked for export, but does '
                     'not have an assigned JIRA ID yet. main.py can create a ticket automatically')

# find steps without ids
shlog.normal('---CHECKING FOR STEPS NOT YET IMPORTED---')
for step in steps:
    if step not in step_tickets.keys():
        shlog.normal('Step ID #' + str(step) + ' (' + steps[step]['Name'] + ') belongs to an exportable activity #' +
                     str(steps[step]['ActivityObjectId']) +
                     ' (' + activities[int(steps[step]['ActivityObjectId'])]['Name'] + '), but does not have a JIRA ID'
                     ' yet. main.py can create a ticket automatically')

# find steps with IDs without a corresponding ticket (different names?)
shlog.normal('---CHECKING FOR ACTIVITIES IMPORTED IMPROPERLY---')
for act in activities:
    issues, count = con.search_for_issue(activities[act]['Name'])
    if count == 0:
        shlog.normal('Could not find Activity "' + activities[act]['Name'] + '" in JIRA')
        if act not in tickets.keys():
            shlog.normal('"' + activities[act]['Name'] + '" does not yet have an associated JIRA ID. '
                                                         'main.py can create a ticket automatically')
        else:
            shlog.normal('"' + activities[act]['Name'] + '" already has a JIRA ID associated with it (' + tickets[act] +')')
            # what will this do
            try:
                # if this suceeds, then the name needs to be synched manually
                jira_tix = con.get_issue(tickets[act])
                shlog.normal('')
            except:
                # if this fails or returns nothing, then the issue needs to be created
                shlog.normal('The specified ticket ' + tickets[act] + ' does not exist. Please fix the JIRA ID record '
                                                                      'or have the main program crate the ticket')
            pass