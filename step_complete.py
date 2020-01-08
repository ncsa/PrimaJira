# this python script will find closed stories in jira and synch back a checkmark to primavera
import main as m
import shlog
import configparser
from jiracmd import Jira
import requests


def post_step_complete(server, user, pw, ObjectId, complete=True):
    url = server + '/p6ws/services/ActivityStepService?wsdl'
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
          <v1:UpdateActivitySteps>
             <v1:ActivityStep>
                <v1:ObjectId>%s</v1:ObjectId>
                <v1:IsCompleted>%s</v1:IsCompleted>
             </v1:ActivityStep>
          </v1:UpdateActivitySteps>
       </soapenv:Body>
    </soapenv:Envelope>""" % (user, pw, ObjectId, str(complete))

    shlog.normal('Post Step ID ' + str(ObjectId) + ' Complete as ' + str(complete) + ' to Primavera server ' + server)
    response = requests.post(url, verify=False, data=body)
    return response.content





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
loglevel=shlog.__dict__[tool_log]
assert type(loglevel) == type(1)
shlog.basicConfig(level=shlog.__dict__[tool_log])
shlog.verbose('Primavera connection will use:\nServer: ' + primaserver +
              '\nUser: ' + primauser + '\nPass: ' + '*'*len(primapasswd))
# init jira stuff
jcon = Jira('jira-section')

m.vpn_toggle(True)
step_tickets = m.get_step_tickets(primaserver, primauser, primapasswd, jcon.server)

# loop through step -> ticket records
for step in step_tickets:
    closed = jcon.check_if_closed(jcon.project, step_tickets[step])
    reopened = jcon.check_if_reopened(jcon.project, step_tickets[step])
    info = m.get_step_info(step, primaserver, primauser, primapasswd)
    if closed:
        shlog.normal('\nREPORTED AS CLOSED\nStep ID: ' + str(step) +
                     '\nStep Name: ' + info['Name'])
        shlog.verbose('\nParent Activity: ' + info['ActivityName'] +
                      '\nJIRA Story: ' + step_tickets[step])
        resp = post_step_complete(primaserver, primauser, primapasswd, step)
    if reopened:
        shlog.normal('\nREPORTED AS REOPENED\nStep ID: ' + str(step) +
                     '\nStep Name: ' + info['Name'])
        shlog.verbose('\nParent Activity: ' + info['ActivityName'] +
                      '\nJIRA Story: ' + step_tickets[step])
        resp = post_step_complete(primaserver, primauser, primapasswd, step, False)

m.vpn_toggle(False)
