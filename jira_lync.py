# this file will link NCSA JIRA and LSST JIRA by linking analog tickets in
# due to this very specific use case, some connection settings are static
# and the login file must contain NCSA JIRA login
import main as m
import configparser
from jiracmd import Jira
import shlog
import jira_utils as ju
import jira


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

    m.vpn_toggle(True)
    # get all NCSA activities and steps with green checkmarks
    synched = m.get_synched_activities(primaserver, primauser, primapasswd, 'https://jira.ncsa.illinois.edu', 'Green')
    activities, steps = m.get_steps_activities(synched, primaserver, primauser, primapasswd)

    # build two dicts with actid to jira ids
    ncsa_tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, 'ncsa')
    lsst_tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, 'lsst')
    ncsa_step_tickets = m.get_step_tickets(primaserver, primauser, primapasswd, 'ncsa')
    lsst_step_tickets = m.get_step_tickets(primaserver, primauser, primapasswd, 'lsst')

    for act in activities:
        # activity must exist both in ncsa and lsst, or there's quite simply nothing to link
        if act in ncsa_tickets.keys() and act in lsst_tickets.keys():
            # print(ncsa_tickets[act] + '//' + lsst_tickets[act])
            try:
                ju.link_second_jira(jcon, ncsa_tickets[act], lsst_tickets[act], 'https://jira.lsstcorp.org')
                shlog.normal('Success linking ' + ncsa_tickets[act] + ' and ' + lsst_tickets[act])
            except (jira.exceptions.JIRAError) as e:
                # jira failures mean we can't sync anything
                shlog.normal('Jira operation faled with error:')
                print(e)
        activity_steps = m.step_list_filter(steps, act)
        for step in activity_steps:
            if step in ncsa_step_tickets.keys() and step in lsst_step_tickets.keys():
                try:
                    ju.link_second_jira(jcon, ncsa_step_tickets[step], lsst_step_tickets[step], 'https://jira.lsstcorp.org')
                    shlog.normal('Success linking ' + ncsa_step_tickets[step] + ' and ' + lsst_step_tickets[step])
                except (jira.exceptions.JIRAError) as e:
                    # jira failures mean we can't sync anything
                    shlog.normal('Jira operation faled with error:')
                    print(e)
    m.vpn_toggle(False)