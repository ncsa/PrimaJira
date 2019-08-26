import jira_utils as ju
from jiracmd import Jira
from zeep import client as c
from zeep.wsse.username import UsernameToken
import configparser
import re

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


# Get all object -> ticket field records
request_data = {
    'Field': ['ForeignObjectId', 'Text', 'ProjectObjectId', 'UDFTypeObjectId'],
    'Filter': "UDFTypeTitle = 'LSST Jira Mapping'"}
wsdl_url = primaserver + '/p6ws/services/UDFValueService?wsdl'
soap_client = c.Client(wsdl_url, wsse=UsernameToken(primauser, primapasswd))
with soap_client.settings(raw_response=False):
    tickets_api = soap_client.service.ReadUDFValues(**request_data)
# create a dict with object -> ticket relations
tickets = {}
for tkt in tickets_api:
    if re.match('[A-Z]+-[0-9]+', tkt.Text):
        tickets.update({tkt.ForeignObjectId: tkt.Text})


# get all activities to sync
request_data = {
    'Field': ['Indicator','ForeignObjectId'],
    'Filter': "UDFTypeTitle = 'Import into JIRA' and Indicator = 'Green'"}
wsdl_url = primaserver + '/p6ws/services/UDFValueService?wsdl'
soap_client = c.Client(wsdl_url, wsse=UsernameToken(primauser, primapasswd))
with soap_client.settings(raw_response=False):
    synched = soap_client.service.ReadUDFValues(**request_data)

for sync in synched:
    # Get information about ACTIVITIES from ActivityService
    request_data = {
        'Field': ['ObjectId', 'Name', 'Id'],
        'Filter': "ObjectId = '%s'" % sync.ForeignObjectId} # replace this with check for JIRA import need
    wsdl_url = primaserver + '/p6ws/services/ActivityService?wsdl'
    soap_client = c.Client(wsdl_url, wsse=UsernameToken(primauser, primapasswd))
    with soap_client.settings(raw_response=False):
        activities_api = soap_client.service.ReadActivities(**request_data)


# reprocess the api response into a more managable dict
activities = {}
# also build a dict of all relevant steps
steps = {}
for act in activities_api:
    activities.update({act.ObjectId : {'Name': act.Name,
                                       'Id': act.Id}})
    # Get information about STEPS from ActivityStepService
    # only needed steps are retrieved to save traffic and execution time
    request_data = {
        'Field': ['ActivityObjectId', 'ObjectId', 'Name', 'Description'],
        'Filter': "ActivityObjectId = '%s'" % act.ObjectId}
    wsdl_url = primaserver + '/p6ws/services/ActivityStepService?wsdl'
    soap_client = c.Client(wsdl_url, wsse=UsernameToken(primauser, primapasswd))
    with soap_client.settings(raw_response=False):
        steps_api = soap_client.service.ReadActivitySteps(**request_data)
    for step in steps_api:
        steps.update({step.ObjectId: {'ActivityObjectId': step.ActivityObjectId,
                                       'Name': step.Name,
                                       'Description': step.Description
                                      }})

# At this point, we have everything to export from Primavera
# This is the Jira section
# ju.create_ticket('jira-section', jcon.user, ticket=None, parent="5", summary='summary', description='descript', project='LSSTTST')
for act in activities:
    if act in tickets.keys():
        # if the ticket already exists, update name etc
        # TODO: put sync logic here
        pass
    else:
        # create a ticket if one doesn't exist
        reqnum, jira_id = ju.create_ticket('jira-section', jcon.user, ticket=None, parent=None, summary=activities[act]['Name'],
                                           description=activities[act]['Name'], use_existing=True, project='LSSTTST',
                                           prima_code=activities[act]['Id'])
        # TODO: POST jira_id back into primavera
        pass
    # go through steps of the activity in question and create their tickets
    for step in steps:
        if steps[step]['ActivityObjectId'] == act:
            ju.create_ticket('jira-section', jcon.user, ticket=None, parent=reqnum, summary=steps[step]['Name'],
                             description=steps[step]['Name'], use_existing=True, project='LSSTTST')
