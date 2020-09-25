import jira_utils as ju
from jiracmd import Jira
from zeep import client as c
from zeep.wsse.username import UsernameToken
from zeep.exceptions import *
import configparser
import re
import requests
import shlog
from requests import Session
from zeep.transports import Transport
import requests
# outta sign, outta mind
requests.packages.urllib3.disable_warnings()
import os
import datetime
import time
import html2text as h
import excel_to_primavera as e


def xmlpost(url, user, pw, ComplexType, element, RequestCore):
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
                  <v1:%s>
                     <v1:%s>
                        %s
                     </v1:%s>
                  </v1:%s>
               </soapenv:Body>
            </soapenv:Envelope>""" % (user, pw, ComplexType, element, RequestCore, element, ComplexType)

    shlog.verbose('Making request to url ' + url)
    shlog.verbose('Request body: ' + body.replace(pw, '*'*len(pw)))
    response = requests.post(url, verify=False, data=body)
    shlog.verbose('Server response: ' + str(response.content))
    return response


def ticket_post(server, user, pw, ForeignObjectId, ProjectObjectId, Text, UDFTypeObjectId):
    url = server + '/p6ws/services/UDFValueService?wsdl'
    core = """<v1:ForeignObjectId>%s</v1:ForeignObjectId>
              <v1:ProjectObjectId>%s</v1:ProjectObjectId>
              <v1:Text>%s</v1:Text>
              <v1:UDFTypeObjectId>%s</v1:UDFTypeObjectId>""" % (ForeignObjectId, ProjectObjectId, Text, UDFTypeObjectId)

    response = xmlpost(url, user, pw, 'CreateUDFValues', 'UDFValue', core)
    return response.content


def multi_ticket_post(server, user, pw, code, Id, jira_id, activity=True):
    if activity:
        # request all activities with the same ID
        shlog.verbose('Making a request to find duplicates for activity Id ' + Id)
        request_data = {'Field': ['ObjectId', 'ProjectObjectId'],
                        'Filter': "Id = '%s'" % Id}
        dupes = soap_request(request_data, server, 'ActivityService', 'ReadActivities', user, pw)
    else:
        # the step request goes off name, because there's no id
        shlog.verbose('Making a request to find duplicates for step named ' + Id)
        request_data = {'Field': ['ObjectId', 'ProjectObjectId'],
                        'Filter': "Name = '%s'" % Id}
        dupes = soap_request(request_data, server, 'ActivityStepService', 'ReadActivitySteps', user, pw)
        if len(dupes) == 0:
            shlog.normal('Critical error: Primavera returned no matches! This is caused by the activity name containing'
                         ' single quotes. Please enter the Story ticket ID manually.')
            return None
    shlog.verbose('Primavera returned ' + str(len(dupes)) + ' duplicates')
    # loop through all of the object ids
    for entry in dupes:
        # delete call
        resp = ticket_wipe(server, user, pw, entry.ObjectId, code)
        # post call
        resp = ticket_post(server, user, pw, entry.ObjectId, entry.ProjectObjectId, jira_id, code)
    return resp



def ticket_wipe(server, user, pw, ForeignObjectId, UDFTypeObjectId):
    request_data = {'ObjectId': {'UDFTypeObjectId': str(UDFTypeObjectId),
                                 'ForeignObjectId': str(ForeignObjectId)}}
    shlog.verbose('Making DeleteUDFValues request for UDFTypeObjectId ' + str(UDFTypeObjectId) + ', ForeignObjectId ' +
                  str(ForeignObjectId))
    response = soap_request(request_data, server, 'UDFValueService', 'DeleteUDFValues', user, pw)
    shlog.verbose('Server response: ' + str(response))
    return response


def soap_request(request_data, primaserver, primaservice, servicereq, user, pw):
    # generic primavera soap requester
    wsdl_url = primaserver + '/p6ws/services/' + primaservice + '?wsdl'
    session = Session()
    session.verify = False
    transport = Transport(session=session)
    soap_client = c.Client(wsdl_url, transport=transport, wsse=UsernameToken(user, pw))
    with soap_client.settings(raw_response=False):
        try:
            api_response = getattr(soap_client.service, servicereq)(**request_data)
        except Fault as error:
            shlog.normal('SOAP request failed with the following:')
            shlog.normal(error.message)
            shlog.normal(error.code)
            shlog.normal(error.actor)
            # do not retry of the error is non-fatal
            if 'ResumeDate: Actual' in error.message:
                # this one is not critical
                shlog.normal('ResumeDate error thrown, ignoring...')
                return
            if 'Unique constraint' in error.message:
                # this one is caused by UDF entry already existing
                shlog.normal('Error! UDF value already exists, skipping...')
                return
            # retry loop
            for i in range(3):
                shlog.normal('Will attempt retry ' + str(i+1) + '/3 in 30 seconds')
                time.sleep(30)
                try:
                    api_response = getattr(soap_client.service, servicereq)(**request_data)
                except:
                    pass
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
        return h.html2text(act_note_api[0]['RawTextNote'])


def get_activity_tickets(server, user, passw, serv):
    # Get all activity -> ticket field records
    if 'ncsa' in serv.lower():
        request_data = {
            'Field': ['ForeignObjectId', 'Text'],
            'Filter': "UDFTypeTitle = 'NCSA Jira Mapping'"}
    if 'lsst' in serv.lower():
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


def get_step_tickets(server, user, passw, serv):
    # Get all step -> ticket field records
    if 'ncsa' in serv.lower():
        request_data = {
            'Field': ['ForeignObjectId', 'Text'],
            'Filter': "UDFTypeTitle = 'NCSA JIRA ID'"}
    if 'lsst' in serv.lower():
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


def get_synched_activities(servr, user, passw, jiraserv, color):
    # get all activities to sync
    if 'ncsa' in jiraserv.lower():
        request_data = {
            'Field': ['Indicator', 'ForeignObjectId'],
            'Filter': "UDFTypeTitle = 'Import into NCSA JIRA' and Indicator = '%s'" % color}
    if 'lsst' in jiraserv.lower():
        request_data = {
            'Field': ['Indicator', 'ForeignObjectId'],
            'Filter': "UDFTypeTitle = 'Import into LSST JIRA' and Indicator = '%s'" % color}
    shlog_list = ''
    for field in request_data['Field']:
        shlog_list += field + ', '
    shlog.verbose('Making Primavera request to get all activities with a ' + color +
                  ' checkmark, fields: ' + shlog_list[:-2])
    synched = soap_request(request_data, servr, 'UDFValueService', 'ReadUDFValues', user, passw)
    return synched


def get_steps_activities(jcon, synched, server, user, passw):
    activities = {}
    steps = {}
    baseline = actual_baseline(server, user, passw)
    for sync in synched:
        # Get information about ACTIVITIES from ActivityService
        request_data = {
            'Field': ['Name', 'Id', 'ProjectId', 'WBSName', 'FinishDate', 'StartDate', 'ActivityOwnerUserId'],
            'Filter': "ObjectId = '%s' and ProjectObjectId = '%d'" % (sync.ForeignObjectId, baseline)}
        shlog_list = ''
        for field in request_data['Field']:
            shlog_list += field + ', '
        shlog.verbose('Making Primavera ActivityService request for ActivityId #' + str(
            sync.ForeignObjectId) + ', fields: ' + shlog_list[:-2] + ' @ BaselineID = ' + str(baseline))
        activities_api = soap_request(request_data, server, 'ActivityService', 'ReadActivities', user, passw)

        if len(activities_api) > 1:
            shlog.normal('\nFATAL ERROR: activities_api returned ' + str(len(activities_api)) + 'results!')
            exit(0)
        if len(activities_api) == 0:
            shlog.verbose('Synched Activity ObjectID ' + str(sync.ForeignObjectId) + ' is not present in Baseline ' +
                          str(baseline) + ', skipping...')
            continue

        activities.update({activities_api[0].ObjectId: {'ProjectId': activities_api[0].ProjectId,
                                                        'Name': activities_api[0].Name,
                                                        'Owner': get_email(jcon, server, user, passw,
                                                                           activities_api[0].ActivityOwnerUserId),
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
                                          'Weight': step.Weight,
                                          'Owner': get_email_step(jcon, server, user, passw,
                                                                  get_step_owner(server, user, passw,
                                                                                 str(step.ObjectId)))
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


def get_step_info(stepid, primaserver, primauser, primapasswd):
    request_data = {
        'Field': ['ActivityId', 'ActivityName', 'Name'],
        'Filter': "ObjectId = '%s'" % stepid}
    api_resp = soap_request(request_data, primaserver, 'ActivityStepService', 'ReadActivitySteps', primauser,
                                    primapasswd)

    try:
        out = {'ActivityId':api_resp[0].ActivityId,
               'ActivityName':api_resp[0].ActivityName,
               'Name':api_resp[0].Name}
    except IndexError:
        out = {'ActivityId':'0',
               'ActivityName':'Error',
               'Name':'Error'}
    return out


def get_act_info(actid, primaserver, primauser, primapasswd):
    request_data = {
        'Field': ['Name', 'Id'],
        'Filter': "ObjectId = '%s'" % actid}
    api_resp = soap_request(request_data, primaserver, 'ActivityService', 'ReadActivities', primauser, primapasswd)

    try:
        out = {'Id':api_resp[0].Id,
               'Name':api_resp[0].Name}
    except IndexError:
        out = {'Id':'0',
               'Name':'Error'}
    return out


def vpn_toggle(switch):
    """issue an OS command to toggle AnyConnect VPN

    :param switch: bool
    :return: None
    """
    import kalm as k
    if switch:
        shlog.normal('Engaging VPN...')
        k.engage()
    if not switch:
        shlog.normal('Disabling VPN...')
        k.disengage()


def get_step_owner(serv, usr, passw, step):
    request_data = {
        'Field': ['Text'],
        'Filter': "ForeignObjectId = '%s'" % str(step)}
    synched = soap_request(request_data, serv, 'UDFValueService', 'ReadUDFValues', usr, passw)

    try:
        return synched[0]['Text']
    except IndexError:
        return None


def actual_baseline(serv, usr, passw):
    """Returns the ObjectID of the most recent and up-to-date baseline

    :param serv: Primavera server
    :param usr: P user
    :param passw: P password
    :return:
    """
    # # request baseline data from the server
    # request_data = {'Field': ['DataDate', 'Name', 'ObjectId']}
    # response = soap_request(request_data, serv, 'BaselineProjectService', 'ReadBaselineProjects', usr, passw)
    # # convert response into a parseable dict
    # baselines = {}
    # for base in response:
    #     baselines[base['ObjectId']] = {'Name' : base['Name'],
    #                                    'Date' : base['DataDate']}
    # # find max value
    # most_recent_obj = max(baselines.keys())
    # most_recent = baselines[most_recent_obj]['Date']
    # most_recent_name = baselines[most_recent_obj]['Name']
    # shlog.verbose('Most recent ProjectObjectId/BaselineId identified as ' + str(most_recent_obj) + ', called ' +
    #               str(most_recent_name) + ' for date ' + str(most_recent))

    # Create activity
    request_data = {'Activity': {'Name': 'Will be deleted in 2 sec',
                                 'AtCompletionDuration': 0,
                                 'CalendarObjectId': 638,  # NCSA Standard with Holidays, ok to hardcode
                                 'ProjectId': 'LSST MREFC',
                                 'WBSObjectId': 4597,
                                 'WBSPath': 'LSST MREFC.MREFC.LSST Construction.Test WBS',  # the big dump
                                 }}
    synched = soap_request(request_data, serv, 'ActivityService', 'CreateActivities', usr, passw)
    created_activity = synched[0]

    # request its baseline id
    request_data = {'Field': ['ProjectObjectId'], 'Filter': "ObjectId = '%s'" % str(created_activity)}
    resp = soap_request(request_data, serv, 'ActivityService', 'ReadActivities', usr, passw)
    most_recent_obj = resp[0]['ProjectObjectId']

    # delete the activity
    request_data = {'ObjectId': '%s' % str(created_activity)}
    synched = soap_request(request_data, serv, 'ActivityService', 'DeleteActivities', usr, passw)

    return most_recent_obj


def get_email(jcon, serv, usr, passw, objectid):
    """get username from activity owner

    :param serv: P server
    :param usr: P user
    :param passw: P password
    :param objectid: ID of activity object
    :return: None or user
    """
    request_data = {'Field': ['EmailAddress', 'Name'],
                    'Filter': "ObjectId = '%s'" % objectid}
    if objectid:  # if it's not None
        synched = soap_request(request_data, serv, 'UserService', 'ReadUsers', usr, passw)
    else:
        return None

    try:
        k = jcon.search_for_user(synched[0]['EmailAddress'], synched[0]['Name'])
        name = k[0].name
        return name
    except IndexError:
        return None


def get_email_step(jcon, serv, usr, passw, name):
    try:
        name = name.replace(',', '')
        name_first = name.split(' ')[0]
        name_last = name.split(' ')[-1]
    except AttributeError:
        return None

    request_data = {'Field': ['EmailAddress', 'Name'],
                    'Filter': "PersonalName like '%%%s%%' and PersonalName like '%%%s%%'" % (name_first, name_last)}
    if name:  # if it's not None
        synched = soap_request(request_data, serv, 'UserService', 'ReadUsers', usr, passw)
    else:
        return None

    try:
        k = jcon.search_for_user(synched[0]['EmailAddress'], synched[0]['Name'])
        name = k[0].name
        return name
    except IndexError:
        return None


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

    vpn_toggle(True)
    # tickets = get_activity_tickets(primaserver, primauser, primapasswd, jcon.server)
    # step_tickets = get_step_tickets(primaserver, primauser, primapasswd, jcon.server)
    synched = get_synched_activities(primaserver, primauser, primapasswd, jcon.server, 'Yellow') #todo change to Yellow
    activities, steps = get_steps_activities(jcon, synched, primaserver, primauser, primapasswd)

    # pass
    # exit(0) # A6830
    # At this point, we have everything to export from Primavera
    # This is the Jira section
    for act in activities:
        # pre-handle steps to get total story points
        activity_steps = step_list_filter(steps, act)
        points = get_total_hours(activity_steps)
        # this will not create duplicates because of a check
        try:
            shlog.normal('Making a request to file a new JIRA Epic or find existing for activity #' + str(act) + ' with:\n'
                         'Name/Summary: ' + str(activities[act]['Name']) + '\nDescription: ' +
                         str(activities[act]['Description']) + '\nProject: ' + str(jcon.project))
        except UnicodeEncodeError:
            shlog.normal('A Unicode error happened when processing ' + activities[act]['Name'] +
                         ', but nobody cared')
        # some presets happen here
        team = None
        if 'ncsa' in jcon.server.lower():
            code = 139
        if 'lsst' in jcon.server.lower():
            code = 130
            team = 'Data Facility'
        reqnum, jira_id = ju.create_ticket('jira-section', activities[act]['Owner'], ticket=None, parent=None,
                                           summary=activities[act]['Name'], description=activities[act]['Description'],
                                           use_existing=True, project=jcon.project,
                                           prima_code=activities[act]['Id'], WBS=activities[act]['WBS'],
                                           start=activities[act]['Start'], due=activities[act]['Due'], spoints=points,
                                           team=team)
        shlog.normal('Returned JIRA ticket ' + jira_id)

        # post if the lsst id needs to be entered
        shlog.normal('Transmitting JIRA ID ' + jira_id + ' back to activity ' + str(act))
        multi_ticket_post(primaserver, primauser, primapasswd, code, activities[act]['Id'], jira_id, True)

        # go through steps of the activity in question and create their tickets
        for step in activity_steps:
            try:
                shlog.normal(
                    'Making a request to file a new JIRA story or find existing for step #' + str(step) + ' with:\n'
                     'Name/Summary: ' + str(steps[step]['Name']) + '\nDescription: ' + str(steps[step]['Description'])
                    + '\nProject: ' + str(jcon.project) + '\nParent: ' + jira_id)
            except UnicodeEncodeError:
                shlog.normal('A Unicode error happened when processing ' + steps[step]['Name'] +
                             ', but nobody cared')
            step_reqnum, step_jira_id = ju.create_ticket('jira-section', steps[step]['Owner'], ticket=None, parent=reqnum,
                                    summary=steps[step]['Name'], description=steps[step]['Description'],
                                    project=jcon.project, spoints=steps[step]['Weight'], team=team)
            shlog.normal('Returned JIRA ticket ' + step_jira_id)

            if 'ncsa' in jcon.server.lower():
                code = 151
            if 'lsst' in jcon.server.lower():
                code = 149
            shlog.normal('Transmitting JIRA ID ' + step_jira_id + ' back to step ' + str(step))
            multi_ticket_post(primaserver, primauser, primapasswd, code, steps[step]['Name'], step_jira_id, False)

        # if we got this far, that means that the activity had been processed succesfully
        # time to post some checkmarks
        if 'ncsa' in jcon.server.lower():
            code = 153
        if 'lsst' in jcon.server.lower():
            code = 148
        e.remove_colors(primaserver, primauser, primapasswd, act, code)
        e.post_color(primaserver, primauser, primapasswd, act, 'Green', code)

    vpn_toggle(False)