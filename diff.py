# diff tool to compare primavera vs jira
# all findings are provided with possible resolutions
import main as m
import shlog
import configparser
import jira_utils as ju
from jiracmd import Jira
import jira


def get_primavera_step_count(ActivityId, server, user, passw):
    request_data = {
        'Field': ['ObjectId'],
        'Filter': "ActivityObjectId = '%s'" % ActivityId}
    steps_api = m.soap_request(request_data, server, 'ActivityStepService', 'ReadActivitySteps', user, passw)
    return len(steps_api)

def fix_it(error_code):
    if error_code == 1:
        # code 1 is Activity JIRA ID present, but ticket doesn't exist
        shlog.normal('Suggested resolution: delete the ticket record from the Activity')
    if error_code == 2:
        shlog.normal('Suggested resolution: delete the ticket record from the Step')
    shlog.normal('Proceed? [y/n]')
    choice = input()
    choice = choice.lower()
    if choice == 'y':
        return True
    else:
        return False

if __name__ == '__main__':
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
    tool_fixer = tool_dict['fix']
    if tool_fixer.lower() in ['true', '1', 't', 'y', 'yes', 'yeah', 'yup', 'certainly', 'uh-huh']:
        tool_fixer = True
    else:
        tool_fixer = False
    loglevel=shlog.__dict__[tool_log]
    assert type(loglevel) == type(1)
    shlog.basicConfig(level=shlog.__dict__[tool_log])
    shlog.verbose('Primavera connection will use:\nServer: ' + primaserver +
                  '\nUser: ' + primauser + '\nPass: ' + '*'*len(primapasswd))
    # init jira stuff
    con = ju.get_con('jira-section')

    m.vpn_toggle(True)
    shlog.verbose('Getting ticket IDs and activities due for export')
    tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, con.server)
    step_tickets = m.get_step_tickets(primaserver, primauser, primapasswd, con.server)
    synched = m.get_synched_activities(primaserver, primauser, primapasswd, con.server, 'Green')
    activities, steps = m.get_steps_activities(con, synched, primaserver, primauser, primapasswd)

    # find activities not yet imported
    shlog.normal('\n---CHECKING FOR ACTIVITIES NOT YET IMPORTED---')
    for act in activities:
        if act not in tickets.keys():
            shlog.normal('Activity #' + str(act) + ' (' + activities[act]['Name'] + ')  is marked for export, but does '
                         'not have an assigned JIRA ID yet. main.py can create a ticket automatically')

    # find steps without ids
    shlog.normal('\n---CHECKING FOR STEPS NOT YET IMPORTED---')
    for step in steps:
        if step not in step_tickets.keys():
            shlog.normal('Step ID #' + str(step) + ' (' + steps[step]['Name'] + ') belongs to an exportable activity #' +
                         str(steps[step]['ActivityObjectId']) +
                         ' (' + activities[int(steps[step]['ActivityObjectId'])]['Name'] + '), but does not have a JIRA ID'
                         ' yet. main.py can create a ticket automatically')

    shlog.normal('\n---CHECKING FOR ACTIVITIES IMPORTED IMPROPERLY---')
    for act in activities:
        issues, count = con.search_for_issue(activities[act]['Name'])
        # find steps with IDs without a corresponding ticket (different names?)
        if count == 0:
            shlog.normal('Could not find Activity "' + activities[act]['Name'] + '" in JIRA, ObjectID: ' + str(act))
            # find unsyched tickets
            if act not in tickets.keys():
                shlog.normal('"' + activities[act]['Name'] + '" does not yet have an associated JIRA ID. '
                                                             'main.py can create a ticket automatically')
            else:
                shlog.normal('"' + activities[act]['Name'] + '" already has a JIRA ID associated with it (' + tickets[act] +')')
                # what will this do
                try:
                    # if this suceeds, then the name needs to be synched manually
                    jira_tix = con.get_issue(tickets[act])
                    shlog.normal('Ticket ' + str(jira_tix) +  " already exists. Please check if it's technically the same "
                                                              "ticket and make the correction manually")
                except:
                    # if this fails or returns nothing, then the record needs to be wiped
                    shlog.normal('The specified ticket ' + tickets[act] + ' does not exist. Please wipe the JIRA ID record '
                                                                          'and/or have the main program create the ticket')
                    if tool_fixer and fix_it(1):
                        if 'ncsa' in con.server.lower():
                            code = 139
                        if 'lsst' in con.server.lower():
                            code = 130
                        m.ticket_wipe(primaserver, primauser, primapasswd, act, code)


        if count == 1:
            # find cases where there is a properly named ticket, but no ticket entry
            if not(tickets.get(act, False)):
                shlog.normal('Ticket with name "' + activities[act]['Name'] + '" exists, but Activity ID #' + str(act) +
                             ' does not have a ticket record. Please add the record manually, or check if activities with '
                             'duplicate names exist')
            # find ticket records mismatches
            if str(tickets.get(act, issues[0].key)) != str(issues[0].key):
                shlog.normal('Activity "' + activities[act]['Name'] + '" has ticket listed as ' + tickets.get(act, False) +
                             ' in Primavera but JIRA returned ticket ' + issues[0].key + '. Please update the record in '
                                                                                         'Primavera if necessary.')
            # find total step story points not adding up to the ticket record
            # pre-handle steps to get total story points
            activity_steps = m.step_list_filter(steps, act)
            p_points = m.get_total_hours(activity_steps)
            try:
                if 'ncsa' in con.server.lower():
                    j_points = int(issues[0].fields.customfield_10532)
                if 'lsst' in con.server.lower():
                    j_points = int(issues[0].fields.customfield_10202)
            except TypeError:
                # caused by field not existing
                j_points = 0
            if j_points != p_points:
                shlog.normal('Activity "' + activities[act]['Name'] + '" has ' + str(p_points) + ' total Story Points '
                             'in Primavera, but JIRA reported ' + str(j_points) + '. Please check for steps not yet '
                             'exported and changes to the Story Points field in JIRA')


        if count > 1:
            shlog.normal('More than one ticket exist with name "' + activities[act]['Name'] + '":')
            for issue in issues:
                shlog.normal(issue.key)
            shlog.normal('Please resolve duplicate tickets')

        try:
            jira_tix = con.get_issue(tickets[act])
            j_stories, j_count = con.search_for_children(con.project,jira_tix)
            p_steps = get_primavera_step_count(act, primaserver, primauser, primapasswd)
            if int(j_count) != int(p_steps):
                shlog.normal('JIRA reported ' + str(j_count) + ' Stories for Epic "' + activities[act]['Name'] + '", '
                             'however Primavera reported ' + str(p_steps) + ' steps for the same activity. Please check'
                             ' for steps that had not been imported or other issues.')
        except (jira.exceptions.JIRAError, KeyError) as e:
            # this usually happens if a ticket does not exist. it's already handled earlier in the code
            # this means that there'sno ticket record in primavera. this is handled elsewhere
            pass

    shlog.normal('\n---CHECKING FOR STEPS IMPORTED IMPROPERLY---')
    for step in steps:
        try:
            # attempt to find the issue not only by name, but also by parent
            parent_activity = int(steps[step]['ActivityObjectId'])
            parent_epic = con.get_issue(tickets[parent_activity])
            issues, count = con.search_for_issue(steps[step]['Name'], parent=parent_epic)
        except (jira.exceptions.JIRAError, KeyError) as e:
            # JIRAError usually happens if a ticket does not exist. it's already handled earlier in the code
            # KeyError means that there's no ticket record in primavera. this is handled elsewhere
            # if any of these issues had caused an error, fall back to searching by name only
            issues, count = con.search_for_issue(steps[step]['Name'], name_only_search=True)

        # find steps with IDs without a corresponding ticket (different names?)
        if count == 0:
            shlog.normal('Could not find Step "' + steps[step]['Name'] + '" (Activity: "' +
                         activities[parent_activity]['Name'] + '") in JIRA, ObjectID: ' + str(step))
            # find unsyched tickets
            if step not in step_tickets.keys():
                shlog.normal('"' + steps[step]['Name'] + '" (Activity: "' +
                             activities[parent_activity]['Name'] + '") does not yet have an '
                             'associated JIRA ID. main.py can create a ticket automatically')
            else:
                shlog.normal('"' + steps[step]['Name'] + '" (Activity: "' +
                             activities[parent_activity]['Name'] + '") already has a JIRA ID '
                             'associated with it (' + step_tickets[step] + ')')
                # what will this do
                try:
                    # if this suceeds, then the name needs to be synched manually
                    jira_tix = con.get_issue(step_tickets[step])
                    shlog.normal('Ticket ' + str(jira_tix) + " already exists. Please check if it's technically the same "
                                                              "ticket and make the correction manually")
                except:
                    # if this fails or returns nothing, then the issue needs to be created
                    shlog.normal('The specified ticket ' + step_tickets[step] + ' does not exist. Please fix the JIRA ID '
                                 'record and/or have the main program create the ticket')
                    if tool_fixer and fix_it(2):
                        if 'ncsa' in con.server.lower():
                            code = 151
                        if 'lsst' in con.server.lower():
                            code = 149
                        m.ticket_wipe(primaserver, primauser, primapasswd, step, code)

        if count == 1:
            # find cases where there is a properly named ticket, but no ticket entry
            if not(step_tickets.get(step, False)):
                shlog.normal('Ticket with name "' + steps[step]['Name'] + '" (Activity: "' +
                             activities[parent_activity]['Name'] + '") exists, but Step ID #' +
                             str(step) + ' does not have a ticket record. Please add the record manually, or check if '
                             'steps with duplicate names exist')
            # find ticket records mismatches
            if str(step_tickets.get(step, issues[0].key)) != str(issues[0].key):
                shlog.normal('Step "' + steps[step]['Name'] + '" (Activity: "' +
                             activities[parent_activity]['Name'] + '") has ticket listed as ' +
                             step_tickets.get(step, False) + ' in Primavera but JIRA returned ticket ' + issues[0].key +
                             '. Please update the record in Primavera if necessary.')
        if count > 1:
            shlog.normal('More than one ticket exists with name ' + steps[step]['Name'] + ':')
            for issue in issues:
                shlog.normal(issue.key)
            shlog.normal('Please resolve duplicate tickets\nThis issue is normally ignored unless issues exist with parent '
                         'ticket')

        # check story pts mismatch
        mismatch = False
        try:
            if 'ncsa' in con.server.lower():
                mismatch = (int(issues[0].fields.customfield_10532) != int(steps[step]['Weight']))
            if 'lsst' in con.server.lower():
                mismatch = (int(issues[0].fields.customfield_10202) != int(steps[step]['Weight']))
        except:
            # this fails due to count being zero
            pass
        if count != 0 and mismatch:
            if 'ncsa' in con.server.lower():
                jirapts = str(issues[0].fields.customfield_10532)
            if 'lsst' in con.server.lower():
                jirapts = str(issues[0].fields.customfield_10202)
            shlog.normal('Step "' + steps[step]['Name'] + '" (Activity: "' +
                         activities[parent_activity]['Name'] + '") reported ' +
                         jirapts + ' story points in JIRA, but ' +
                         str(steps[step]['Weight']) + ' weight in Primavera')

    m.vpn_toggle(False)
