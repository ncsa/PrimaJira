import jira_utils as ju
from jiracmd import Jira
from zeep import client as c
from zeep.wsse.username import UsernameToken
import configparser

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
# ju.create_ticket('jira-section', jcon.user, ticket=None, parent="5", summary='summary', description='descript', project='LSSTTST')

# Enterprise Project Structure
request_data = {
    'Field': 'Name'}
wsdl_url = 'https://uofi-stage-p6.oracleindustry.com/p6ws/services/EPSService?wsdl'
soap_client = c.Client(wsdl_url, wsse=UsernameToken(primauser, primapasswd))
# with soap_client.settings(raw_response=False):
#     api_result = soap_client.service.ReadEPS(**request_data)
pass

# ActivityStepService
request_data = {
    'Field': ['ActivityName', 'ActivityId']}
wsdl_url = 'https://uofi-stage-p6.oracleindustry.com/p6ws/services/ActivityStepService?wsdl'
soap_client = c.Client(wsdl_url, wsse=UsernameToken(primauser, primapasswd))
with soap_client.settings(raw_response=False):
    api_result = soap_client.service.ReadActivitySteps(**request_data)
pass

# ActivityService
request_data = {
    'Field': 'WBSName'}
wsdl_url = 'https://uofi-stage-p6.oracleindustry.com/p6ws/services/ActivityService?wsdl'
soap_client = c.Client(wsdl_url, wsse=UsernameToken(primauser, primapasswd))
with soap_client.settings(raw_response=False):
    api_result = soap_client.service.ReadActivities(**request_data)
pass