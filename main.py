import jira_utils as ju
from jiracmd import Jira

jcon = Jira('jira-section')

ju.create_ticket('jira-section', jcon.user, ticket=None, parent="5", summary='summary', description='descript', project='LSSTTST')