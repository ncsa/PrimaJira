# init
import configparser
import shlog
import main as m
from jiracmd import Jira
import diff as d
import jira
import html2text as h
from fuzzywuzzy import fuzz
from fuzzywuzzy import process


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
# init jira connection
con = Jira('jira-section')
# read tool config
tool_dict = parser['tool-settings']
tool_log = tool_dict['loglevel']
loglevel=shlog.__dict__[tool_log]
assert type(loglevel) == type(1)
shlog.basicConfig(level=shlog.__dict__[tool_log])
tool_fixer = tool_dict['fix']


def parent_has_step(server, usr, passw, parent, name):
    # get step list
    request_data = {
        'Field': ['ObjectId','Name'],
        'Filter': "ActivityObjectId = '%s'" % parent}
    shlog_list = ''
    for field in request_data['Field']:
        shlog_list += field + ', '
    shlog.verbose('Requesting if Activity #' + str(parent) + ' has step ' + name + ', fields: ' + shlog_list[:-2])
    steps_api = m.soap_request(request_data, server, 'ActivityStepService', 'ReadActivitySteps', usr, passw)

    # run CASE INSENSITIVE SPECE-REMOVING check against the results
    result = None
    for step in steps_api:
        confidence = fuzz.WRatio(step['Name'], name)
        shlog.normal('Comparing:\nJIRA: ' + name + '\nP6: ' + step['Name'] + '\nConfidence: '
                     + str(confidence))
        if confidence >= 94:
            result = step['ObjectId']
            break
    return result


def get_step_baseline(server, usr, passw, objectid):
    # request step's baseline id
    request_data = {'Field': ['ProjectObjectId'], 'Filter': "ObjectId = '%s'" % str(objectid)}
    resp = m.soap_request(request_data, server, 'ActivityStepService', 'ReadActivitySteps', usr, passw)
    return resp[0]['ProjectObjectId']

def update_step_desc(server, usr, passw, parent, objectid, desc):
    request_data = {'ActivityStep': {'ActivityObjectId': parent,
                                     'ObjectId': objectid,
                                     'Description': desc}}
    synched = m.soap_request(request_data, server, 'ActivityStepService', 'UpdateActivitySteps', usr, passw)
    return synched


if __name__ == '__main__':
    # get epic list
    # m.vpn_toggle(True)
    shlog.verbose('Getting ticket IDs and activities to analyze')
    tickets = m.get_activity_tickets(primaserver, primauser, primapasswd, con.server)
    step_tickets = m.get_step_tickets(primaserver, primauser, primapasswd, con.server)
    # synched = m.get_synched_activities(primaserver, primauser, primapasswd, con.server, 'Green')
    # activities, steps = m.get_steps_activities(con, synched, primaserver, primauser, primapasswd)
    # pick the right UDF field
    if 'ncsa' in con.server.lower():
        code = 151
    if 'lsst' in con.server.lower():
        code = 149


    # go through it, comparing activity vs epic step count
    for act in tickets:
        try:
            # check if activity epic exists
            jira_tix = con.get_issue(tickets[act])
            # get jira ticket stats
            j_stories, j_count = con.search_for_children(con.project, jira_tix)
            # get p6 step count
            p_steps = d.get_primavera_step_count(act, primaserver, primauser, primapasswd)
            shlog.normal('________________________________')
            shlog.normal('Epic: ' + jira_tix.fields.summary)
            shlog.normal('Ticket ID: ' + str(jira_tix))
            shlog.normal('JIRA: ' + str(j_count) +
                         ' stories// Primavera: ' + str(p_steps) + ' steps')
            # find subtickets missing from p6
            for story in j_stories:
                if str(story) not in step_tickets.values():
                    shlog.verbose(str(story) + ' not in ticket list')

                    # get story points from the right field
                    try:
                        if 'ncsa' in con.server.lower():
                            j_points = int(story.fields.customfield_10532)
                        if 'lsst' in con.server.lower():
                            j_points = int(story.fields.customfield_10202)
                    except TypeError:
                        # caused by field not existing
                        j_points = 0

                    # check if the parent already has this step
                    step_id = parent_has_step(primaserver, primauser, primapasswd, act, story.fields.summary)
                    if step_id is not None:
                        # the step already exists! good thing we checked
                        shlog.verbose('Step for ' + str(story) + ' already exists, called ' + story.fields.summary)
                        # the universal posting part will do its job
                        resp = update_step_desc(primaserver, primauser, primapasswd, act, step_id,
                                                story.fields.description)
                    else:
                        shlog.verbose('Step for ticket ' + str(story) + ' does not exist')

                        # make a creation request
                        request_data = {'ActivityStep': {'ActivityObjectId': act,
                                                         'Description': story.fields.description,
                                                         'Name': str(story.fields.summary)[:119],
                                                         'Weight': j_points}}
                        shlog_list = ''
                        for field in request_data['ActivityStep']:
                            shlog_list += field + ', '
                        shlog.verbose('Creating step, fields: ' + shlog_list[:-2])
                        synched = m.soap_request(request_data, primaserver, 'ActivityStepService', 'CreateActivitySteps',
                                                 primauser, primapasswd)
                        shlog.verbose('Server response: ' + str(synched))
                        step_id = synched[0]

                    baseline = get_step_baseline(primaserver, primauser, primapasswd, step_id)
                    # post jira id
                    shlog.verbose('Posting ' + str(story) + ' to step ' + str(step_id))
                    # delete call, just in case there's a wong ticket punched in
                    resp = m.ticket_wipe(primaserver, primauser, primapasswd, step_id, code)
                    resp = m.ticket_post(primaserver, primauser, primapasswd, step_id, baseline, str(story), code)
        except (jira.exceptions.JIRAError, KeyError) as e:
            # this usually happens if a ticket does not exist. it's already handled earlier in the code
            # this means that there'sno ticket record in primavera. this is handled elsewhere
            shlog.normal('Unable to find ticket ' + tickets[act])
        # get primavera step count

        # completedness is handled elsewhere (by a cron job)
        # add different jira handling





# if there are more steps in epic, import step to jira