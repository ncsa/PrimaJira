import jira_utils as ju
from jiracmd import Jira
from zeep import client as c
from zeep.wsse.username import UsernameToken
import configparser
import re
import requests


def ticket_post(user, pw, ForeignObjectId, ProjectObjectId, Text, UDFTypeObjectId):
    url = 'https://uofi-stage-p6.oracleindustry.com/p6ws/services/UDFValueService?wsdl'
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


# read config and get primavera login info
parser = configparser.ConfigParser()
with open('login') as configfile:
    parser.read_file(configfile)
primadict=parser['primavera-section']
primauser=primadict['user']
primapasswd=primadict['passwd']
primaserver=primadict['server']
# init jira and primavera connections
jcon = Jira('jira-section')


# Get all activity -> ticket field records
request_data = {
    'Field': ['ForeignObjectId', 'Text'],
    'Filter': "UDFTypeTitle = 'LSST Jira Mapping'"}
tickets_api = soap_request(request_data, primaserver, 'UDFValueService', 'ReadUDFValues', primauser, primapasswd)
# create a dict with activity -> ticket relations
tickets = {}
for tkt in tickets_api:
    if re.match('[A-Z]+-[0-9]+', tkt.Text):
        tickets.update({tkt.ForeignObjectId: tkt.Text})

# Get all step -> ticket field records
request_data = {
    'Field': ['ForeignObjectId', 'Text'],
    'Filter': "UDFTypeTitle = 'LSST JIRA ID'"}
step_tickets_api = soap_request(request_data, primaserver, 'UDFValueService', 'ReadUDFValues', primauser, primapasswd)
# create a dict with step -> ticket relations
step_tickets = {}
for tkt in step_tickets_api:
    if re.match('[A-Z]+-[0-9]+', tkt.Text):
        step_tickets.update({tkt.ForeignObjectId: tkt.Text})

# get all activities to sync
request_data = {
    'Field': ['Indicator','ForeignObjectId'],
    'Filter': "UDFTypeTitle = 'Import into JIRA' and Indicator = 'Green'"}
synched = soap_request(request_data, primaserver, 'UDFValueService', 'ReadUDFValues', primauser, primapasswd)

activities = {}
steps = {}
for sync in synched:
    # Get information about ACTIVITIES from ActivityService
    request_data = {
        'Field': ['Name', 'Id', 'ProjectId'],
        'Filter': "ObjectId = '%s'" % sync.ForeignObjectId} # replace this with check for JIRA import need
    activities_api = soap_request(request_data, primaserver, 'ActivityService', 'ReadActivities', primauser, primapasswd)

    for act in activities_api:
        activities.update({act.ObjectId : {'ProjectId': act.ProjectId,
                                           'Name': act.Name,
                                           'Id': act.Id}})
        # Get information about STEPS from ActivityStepService
        # only needed steps are retrieved to save traffic and execution time
        request_data = {
            'Field': ['ActivityObjectId', 'ObjectId', 'Name', 'Description', 'ProjectId'],
            'Filter': "ActivityObjectId = '%s'" % act.ObjectId}
        steps_api = soap_request(request_data, primaserver, 'ActivityStepService', 'ReadActivitySteps', primauser, primapasswd)
        for step in steps_api:
            steps.update({step.ObjectId: {'ActivityObjectId': step.ActivityObjectId,
                                          'Name': step.Name,
                                          'Description': step.Description,
                                          'ProjectId': step.ProjectId
                                          }})


# At this point, we have everything to export from Primavera
# This is the Jira section
for act in activities:
    # this will not create duplicates because of a check
    reqnum, jira_id = ju.create_ticket('jira-section', jcon.user, ticket=None, parent=None,
                                       summary=activities[act]['Name'],
                                       description=activities[act]['Name'], use_existing=True, project='LSSTTST',
                                       prima_code=activities[act]['Id'])
    if act in tickets.keys():
        # if the ticket already exists, update name etc
        # TODO: put sync logic here
        # TODO: add a check to see if the ticket id reported by jira matches the one on the record
        pass
    else:
        # post if the lsst id needs to be entered
        resp = ticket_post(primauser, primapasswd, act, activities[act]['ProjectId'], jira_id, 130)
    # go through steps of the activity in question and create their tickets
    for step in steps:
        if steps[step]['ActivityObjectId'] == act:
            if step in step_tickets.keys():
                # TODO: add sync here
                pass
            else:
                step_reqnum, step_jira_id = ju.create_ticket('jira-section', jcon.user, ticket=None, parent=reqnum,
                                        summary=steps[step]['Name'], description=steps[step]['Name'], project='LSSTTST')
                resp = ticket_post(primauser, primapasswd, step, steps[step]['ProjectId'], step_jira_id, 329)