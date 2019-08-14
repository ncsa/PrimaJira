import jira_utils as ju
from jiracmd import Jira
from zeep import client as c
from zeep.wsse.username import UsernameToken

jcon = Jira('jira-section')

# make request to primavera
# convert json output to an in-memory table
# loop the following code
# ju.create_ticket('jira-section', jcon.user, ticket=None, parent="5", summary='summary', description='descript', project='LSSTTST')

request_data = {
    'Field': 'ActivityId'
}

wsdl_url = 'https://uofi-stage-p6.oracleindustry.com/p6ws/services/ActivityStepService?wsdl'
soap_client = c.Client(wsdl_url, wsse=UsernameToken("EKIMTCOV", ""))
with soap_client.settings(raw_response=True):
    weather_api_result = soap_client.service.ReadActivitySteps(**request_data)
deer = dir(weather_api_result)

attr_dump = []
for attrib in deer:
    x = getattr(weather_api_result, attrib)
    attr_dump.append(x)
    pass

print(weather_api_result.__dict__)
print(weather_api_result.__str__)