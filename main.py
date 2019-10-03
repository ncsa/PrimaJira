import jira_utils as ju
from jiracmd import Jira
from zeep import client as c
from zeep.wsse.username import UsernameToken
import configparser
import re
import requests
import shlog


def ticket_post(server, user, pw, ForeignObjectId, ProjectObjectId, Text, UDFTypeObjectId):
    url = server + '/p6ws/services/UDFValueService?wsdl'
    body = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:v1="http://xmlns.oracle.com/Primavera/P6/WS/UDFValue/V1">
       <soapenv:Header>
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
          <wsse:UsernameToken>
            <wsse:Username>%s</wsse:Username>
            <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">%s</wsse:Password>
          </wsse:UsernameToken>
        </wsse:Security>
      </soapenv:Header>
       <soapenv:Body>
          <v1:CreateUDFValues>
             <v1:UDFValue>
                <v1:ForeignObjectId>%s</v1:ForeignObjectId>
                <v1:ProjectObjectId>%s</v1:ProjectObjectId>
                <v1:Text>%s</v1:Text>
                <v1:UDFTypeObjectId>%s</v1:UDFTypeObjectId>
             </v1:UDFValue>
          </v1:CreateUDFValues>
       </soapenv:Body>
    </soapenv:Envelope>""" % (user, pw, ForeignObjectId, ProjectObjectId, Text, UDFTypeObjectId)

    response = requests.post(url, data=body)
    return response.content


def soap_request(request_data, primaserver, primaservice, servicereq, user, pw):
    # generic primavera soap requester
    wsdl_url = primaserver + '/p6ws/services/' + primaservice + '?wsdl'
    soap_client = c.Client(wsdl_url, wsse=UsernameToken(user, pw))
    with soap_client.settings(raw_response=False):
        api_response = getattr(soap_client.service, servicereq)(**request_data)
    return api_response

def get_activity_scope(act_id, primaserver, user, pw):
    # attempt to retrieve the scope notebook record of the activity
    request_data = {
        'Field': ['RawTextNote'],
        'Filter': "ActivityObjectId = '%s' and NotebookTopicName = 'Scope'" % str(act_id)}
    shlog_list = ''
    for field in request_data['Field']:
        shlog_list += field + ', '
    shlog.verbose('Making Primavera ActivityNoteService request for the description of activity ActivityId #'
                  + str(act_id) + ', fields: ' + shlog_list[:-2])
    act_note_api = soap_request(request_data, primaserver, 'ActivityNoteService', 'ReadActivityNotes', user, pw)
    if len(act_note_api) == 0:
        return None
    else:
        return act_note_api[0]['RawTextNote']


def get_activity_tickets(server, user, passw):
    # Get all activity -> ticket field records
    request_data = {
        'Field': ['ForeignObjectId', 'Text'],
        'Filter': "UDFTypeTitle = 'LSST Jira Mapping'"}
    shlog_list = ''
    for field in request_data['Field']:
        shlog_list += field + ', '
    shlog.verbose('Making Primavera request to get all activities with recorded Epics, fields: ' + shlog_list[:-2])
    tickets_api = soap_request(request_data, server, 'UDFValueService', 'ReadUDFValues', user, passw)
    # create a dict with activity -> ticket relations
    tickets = {}
    for tkt in tickets_api:
        try:
            if re.match('[A-Z]+-[0-9]+', tkt.Text):
                tickets.update({tkt.ForeignObjectId: tkt.Text})
        except TypeError:
            # caused by "None" values
            pass
    return tickets


def get_step_tickets(server, user, passw):
    # Get all step -> ticket field records
    request_data = {
        'Field': ['ForeignObjectId', 'Text'],
        'Filter': "UDFTypeTitle = 'LSST JIRA ID'"}
    shlog_list = ''
    for field in request_data['Field']:
        shlog_list += field + ', '
    shlog.verbose('Making Primavera request to get all steps with recorded Stories, fields: ' + shlog_list[:-2])
    step_tickets_api = soap_request(request_data, server, 'UDFValueService', 'ReadUDFValues', user, passw)
    # create a dict with step -> ticket relations
    step_tickets = {}
    for tkt in step_tickets_api:
        try:
            if re.match('[A-Z]+-[0-9]+', tkt.Text):
                step_tickets.update({tkt.ForeignObjectId: tkt.Text})
        except TypeError:
            # type error might be caused by None values. ignore error.
            pass
    return step_tickets


def get_synched_activities(servr, user, passw):
    # get all activities to sync
    request_data = {
        'Field': ['Indicator', 'ForeignObjectId'],
        'Filter': "UDFTypeTitle = 'Import into JIRA' and Indicator = 'Green'"}
    shlog_list = ''
    for field in request_data['Field']:
        shlog_list += field + ', '
    shlog.verbose('Making Primavera request to get all activities with a '
                  'green checkmark ready for export, fields: ' + shlog_list[:-2])
    synched = soap_request(request_data, servr, 'UDFValueService', 'ReadUDFValues', user, passw)
    return synched


def get_steps_activities(synched, server, user, passw):
    activities = {}
    steps = {}
    for sync in synched:
        # Get information about ACTIVITIES from ActivityService
        request_data = {
            'Field': ['Name', 'Id', 'ProjectId', 'WBSName', 'FinishDate', 'StartDate'],
            'Filter': "ObjectId = '%s'" % sync.ForeignObjectId}
        shlog_list = ''
        for field in request_data['Field']:
            shlog_list += field + ', '
        shlog.verbose('Making Primavera ActivityService request for ActivityId #' + str(
            sync.ForeignObjectId) + ', fields: ' + shlog_list[:-2])
        activities_api = soap_request(request_data, server, 'ActivityService', 'ReadActivities', user, passw)

        if len(activities_api) > 1:
            shlog.normal('\nFATAL ERROR: activities_api returned ' + str(len(activities_api)) + 'results!')
            exit(0)

        activities.update({activities_api[0].ObjectId: {'ProjectId': activities_api[0].ProjectId,
                                                        'Name': activities_api[0].Name,
                                                        'Id': activities_api[0].Id,
                                                        'WBS': wbs_extractor(activities_api[0].WBSName),
                                                        'Start': activities_api[0].StartDate,
                                                        'Due': activities_api[0].FinishDate,
                                                        'Description': get_activity_scope(activities_api[0].ObjectId,
                                                                                          server, user,
                                                                                          passw)}})
        # Get information about STEPS from ActivityStepService
        # only needed steps are retrieved to save traffic and execution time
        request_data = {
            'Field': ['ActivityObjectId', 'ObjectId', 'Name', 'Description', 'ProjectId', 'Weight'],
            'Filter': "ActivityObjectId = '%s'" % activities_api[0].ObjectId}
        shlog_list = ''
        for field in request_data['Field']:
            shlog_list += field + ', '
        shlog.verbose('Making Primavera ActivityStepService request for all steps of activity ActivityId #'
                      + str(sync.ForeignObjectId) + ', fields: ' + shlog_list[:-2])
        steps_api = soap_request(request_data, server, 'ActivityStepService', 'ReadActivitySteps', user, passw)
        shlog.verbose('Found ' + str(len(steps_api)) + ' steps')
        for step in steps_api:
            steps.update({step.ObjectId: {'ActivityObjectId': step.ActivityObjectId,
                                          'Name': step.Name,
                                          'Description': step.Description,
                                          'ProjectId': step.ProjectId,
                                          'Weight': step.Weight
                                          }})
    return activities, steps

def wbs_extractor(raw):
    try:
        return re.search('\S+(\.\S)+([^" "]+)', raw).group(0)
    except AttributeError:
        return None


def step_list_filter(steps, ActivityID):
    output = {}
    for step in steps:
        if steps[step]['ActivityObjectId'] == ActivityID:
            output[step] = steps[step]
    return output


def get_total_hours(steps):
    pts = 0
    for step in steps:
        pts += steps[step]['Weight']
    return pts


# read config
parser = configparser.ConfigParser()
with open('login') as configfile:
        parser.read_file(configfile)
# read tool config
tool_dict = parser['tool-settings']
tool_log = tool_dict['loglevel']
loglevel = shlog.__dict__[tool_log]
assert type(loglevel) == type(1)
shlog.basicConfig(level=shlog.__dict__[tool_log])

if __name__ == '__main__':
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

    tickets = get_activity_tickets(primaserver, primauser, primapasswd)
    step_tickets = get_step_tickets(primaserver, primauser, primapasswd)
    synched = get_synched_activities(primaserver, primauser, primapasswd)
    activities, steps = get_steps_activities(synched, primaserver, primauser, primapasswd)


    # At this point, we have everything to export from Primavera
    # This is the Jira section
    for act in activities:
        # pre-handle steps to get total story points
        activity_steps = step_list_filter(steps, act)
        points = get_total_hours(activity_steps)
        # this will not create duplicates because of a check
        shlog.normal('Making a request to file a new JIRA Epic or find existing for activity #' + str(act) + ' with:\n'
                     'Name/Summary: ' + str(activities[act]['Name']) + '\nDescription: ' +
                     str(activities[act]['Description']) + '\nProject: ' + str(jiraproject))
        reqnum, jira_id = ju.create_ticket('jira-section', None, ticket=None, parent=None,
                                           summary=activities[act]['Name'],
                                           description=activities[act]['Description'], use_existing=True, project=jiraproject,
                                           prima_code=activities[act]['Id'], WBS=activities[act]['WBS'],
                                           start=activities[act]['Start'], due=activities[act]['Due'], spoints=points)
        shlog.normal('Returned JIRA ticket ' + jira_id)
        if act in tickets.keys():
            # if the ticket already exists, update name etc
            # TODO: put sync logic here
            # TODO: add a check to see if the ticket id reported by jira matches the one on the record
            pass
        else:
            # post if the lsst id needs to be entered
            shlog.normal('Transmitting JIRA ID ' + jira_id + ' back to activity ' + str(act))
            resp = ticket_post(primaserver, primauser, primapasswd, act, activities[act]['ProjectId'], jira_id, 130)
        # go through steps of the activity in question and create their tickets
        for step in activity_steps:
            if step in step_tickets.keys():
                # TODO: add sync here
                pass
            else:
                shlog.normal(
                    'Making a request to file a new JIRA story or find existing for step #' + str(step) + ' with:\n'
                     'Name/Summary: ' + str(steps[step]['Name']) + '\nDescription: ' + str(steps[step]['Description'])
                    + '\nProject: ' + str(jiraproject) + '\nParent: ' + jira_id)
                step_reqnum, step_jira_id = ju.create_ticket('jira-section', None, ticket=None, parent=reqnum,
                                        summary=steps[step]['Name'], description=steps[step]['Description'],
                                        project='DM', spoints=steps[step]['Weight'])
                shlog.normal('Returned JIRA ticket ' + step_jira_id)
                resp = ticket_post(primaserver, primauser, primapasswd, step, steps[step]['ProjectId'], step_jira_id, 149)
                shlog.normal('Transmitting JIRA ID ' + step_jira_id + ' back to step ' + str(step))