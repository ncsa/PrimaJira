import configparser
import shlog
from jiracmd import Jira
import main as m


def jira_status_translator(source_status):
    if source_status in ['To Do', 'Open', 'System Change Control', 'Reopened', 'Backlog']:
        return 'To Do'
    if source_status in ['In Progress', 'Blocked', 'Waiting on User', 'Sleeping']:
        return 'In Progress'
    if source_status in ['Closed']:
        return 'Done'


# read config and get primavera login info
parser = configparser.ConfigParser()
with open('login') as configfile:
    parser.read_file(configfile)
primadict=parser['primavera-section']
primauser=primadict['user']
primapasswd=primadict['passwd']
primaserver=primadict['server']

# read jira info for verbose output
jiradict = parser['jira-section']
jiraproject = jiradict['project']
shlog.verbose('Primavera connection will use:\nServer: ' + primaserver +
              '\nUser: ' + primauser + '\nPass: ' + '*' * len(primapasswd))

# init source and target jiras
con = Jira('jira-section')
con_target = Jira('jira-target')


# read tool config
tool_dict = parser['tool-settings']
tool_log = tool_dict['loglevel']
loglevel=shlog.__dict__[tool_log]
assert type(loglevel) == type(1)
shlog.basicConfig(level=shlog.__dict__[tool_log])
tool_fixer = tool_dict['fix']

if __name__ == '__main__':
    # get epic list
    m.vpn_toggle(True)
    # get ncsa tickets
    ncsa_tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, con.server)
    ncsa_step_tickets = m.get_step_tickets(primaserver, primauser, primapasswd, con.server)
    # get lsst tickets
    lsst_tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, con_target.server)
    lsst_step_tickets = m.get_step_tickets(primaserver, primauser, primapasswd, con_target.server)
    
    # loop through ncsa tickets and get their statuses
    for ncsa_ticket in ncsa_tickets:
        # check if there's a matching LSST ticket
        if ncsa_ticket in lsst_tickets:
            ncsa_jira_id = ncsa_tickets[ncsa_ticket]
            lsst_jira_id = lsst_tickets[ncsa_ticket]
            issue = con.get_issue(ncsa_jira_id)
            if issue:
                status = str(issue.fields.status)
                shlog.verbose('Processing ticket ' + ncsa_jira_id + ' with status ' + status)
                lsst_status = jira_status_translator(status)
                con_target.post_status(lsst_jira_id,lsst_status)
            else:
                # the issue is not present in JIRA
                shlog.verbose(ncsa_jira_id + " doesn't exist!")
                continue

    # same as above for subissues
    for ncsa_ticket in ncsa_step_tickets:
        # check if there's a matching LSST ticket
        if ncsa_ticket in lsst_step_tickets:
            ncsa_jira_id = ncsa_step_tickets[ncsa_ticket]
            lsst_jira_id = lsst_step_tickets[ncsa_ticket]
            issue = con.get_issue(ncsa_jira_id)
            if issue:
                status = str(issue.fields.status)
                shlog.verbose('Processing ticket ' + ncsa_jira_id + ' with status ' + status)
                lsst_status = jira_status_translator(status)
                con_target.post_status(lsst_jira_id,lsst_status)
            else:
                # the issue is not present in JIRA
                shlog.verbose(ncsa_jira_id + " doesn't exist!")
                continue

# concerns: wontfix, LSST-2144//DM-18822