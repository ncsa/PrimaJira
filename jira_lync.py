# this file will link NCSA JIRA and LSST JIRA by linking analog tickets in
# due to this very specific use case, some connection settings are static
# and the login file must contain NCSA JIRA login
import main as m
import configparser
from jiracmd import Jira
import shlog
import jira_utils as ju


if __name__ == '__main__':
    # read config and get primavera login info
    parser = configparser.ConfigParser()
    with open('login') as configfile:
        parser.read_file(configfile)
    # read primavera config
    primadict = parser['primavera-section']
    primauser = primadict['user']
    primapasswd = primadict['passwd']
    primaserver = primadict['server']
    # read jira info for verbose output
    jiradict = parser['jira-section']
    jiraproject = jiradict['project']
    shlog.verbose('Primavera connection will use:\nServer: ' + primaserver +
                  '\nUser: ' + primauser + '\nPass: ' + '*' * len(primapasswd))
    # init jira connection
    jcon = Jira('jira-section')

    # get all NCSA activities and steps with green checkmarks
    synched = m.get_synched_activities(primaserver, primauser, primapasswd, 'https://jira.ncsa.illinois.edu')
    activities, steps = m.get_steps_activities(synched, primaserver, primauser, primapasswd)

    # build two dicts with actid to jira ids
    ncsa_tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, 'ncsa')
    lsst_tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, 'lsst')


    for act in activities:
        # activity must exist both in ncsa and lsst, or there's quite simply nothing to link
        if act in ncsa_tickets.keys() and act in lsst_tickets.keys():
            # print(ncsa_tickets[act] + '//' + lsst_tickets[act])
            ju.link_second_jira(jcon, ncsa_tickets[act], lsst_tickets[act], 'https://jira.lsstcorp.org')
            # add step linking too
