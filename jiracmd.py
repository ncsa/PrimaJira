# jiracmd.py originally developed by Michael D Johnson
# https://github.com/Michael-D-Johnson/desdm-dash/blob/docker/app/jiracmd.py
#! /usr/bin/env python

import os
import sys
from jira.client import JIRA
import configparser
import shlog
from datetime import datetime
import jira
import requests
from requests.auth import HTTPBasicAuth
import json
import networkx as nx


# init logger
parser = configparser.ConfigParser()
with open('login') as configfile:
    parser.read_file(configfile)
tool_dict = parser['tool-settings']
tool_log = tool_dict['loglevel']
loglevel=shlog.__dict__[tool_log]
assert type(loglevel) == type(1)
shlog.basicConfig(level=shlog.__dict__[tool_log])

class Jira:
    def __init__(self,section):
        parser = configparser.ConfigParser()
        with open('login') as configfile:
            parser.read_file(configfile)
        jiradict=parser[section]
        jirauser=jiradict['user']
        jirapasswd=jiradict['passwd']
        jiraserver=jiradict['server']
        jiraproject = jiradict['project']
        jiraworkflow = jiradict['workflow']
        jira=JIRA(options={'server':jiraserver},basic_auth=(jirauser,jirapasswd))
        self.jira = jira
        self.server = jiraserver
        self.user = jirauser
        self.project = jiraproject
        self.workflow = jiraworkflow
        self.pw = jirapasswd
        shlog.verbose('JIRA connection will use:\nServer: ' + jiraserver +
                      '\nUser: ' + jirauser + '\nPass: ' + '*'*len(jirapasswd) + '\nProject: ' + jiraproject)


    def transitionX(self, start, desired):
        wf_url = self.workflow.replace(' ','%20')
        url = self.server + "/rest/projectconfig/1/workflow?workflowName=" + wf_url + "&projectKey=" + self.project
        auth = HTTPBasicAuth(self.user, self.pw)
        headers = {"Accept": "application/json"}
        response = requests.request("GET", url, headers=headers, auth=auth)

        # networkx starts here
        nodes = []
        edges = []
        workflow = json.loads(response.text)
        for source in workflow['sources']:
            source_name = source['fromStatus']['name']
            # print(source_name)
            # add node to node list
            nodes.append(source_name)
            for target in source['targets']:
                target_name = target['toStatus']['name']
                # print('     ' + target_name)
                # add edge to edge list
                edges.append((source_name, target_name))
            # print('______')

        # now that we have the nodes and edges, we can construct the
        g = nx.DiGraph()
        g.add_nodes_from(nodes)
        g.add_edges_from(edges)
        try:
            return nx.shortest_path(g, start, desired)
        except nx.exception.NetworkXNoPath:
            shlog.normal('No path found between ' + start + ' and ' + target)
            return None

    def search_for_issue(self,summary,parent=None, name_only_search=False):
        summary = summary.replace('"','') # checked - search still works the same
        if parent:
            jql = '''summary ~ "\\"%s\\"" and "Epic Link" = "%s"''' % (summary, parent)
        else:
            jql = '''summary ~ "\\"%s\\"" and issuetype = Epic''' % (summary)
        if name_only_search:
            jql = '''summary ~ "\\"%s\\""''' % (summary)
        shlog.verbose('Issuing JQL query: ' + jql)
        issue = self.jira.search_issues(jql)
        count = len(issue)
        return (issue,count)

    def search_for_parent(self,project,summary):
        summary = summary.replace('"', '')  # checked - search still works the same
        jql = '''project = "%s" and summary ~ "%s"''' % (project, summary)
        shlog.verbose('Issuing JQL query: ' + jql)
        issue = self.jira.search_issues(jql)
        count = len(issue)
        return (issue,count)

    def search_for_children(self,project,parent):
        jql = 'project = "%s" and "Epic Link" = "%s"' % (project, parent)
        shlog.verbose('Issuing JQL query: ' + jql)
        issue = self.jira.search_issues(jql)
        count = len(issue)
        return (issue, count)

    def get_issue(self,key):
        try:
            issue_info = self.jira.issue(key)
        except jira.exceptions.JIRAError:
            # triggered by issue not existing
            shlog.normal(key + " not found!")
            return None
        return issue_info

    def get_available_statuses(self):
        return self.jira.statuses()

    def post_status(self,ticket,status):
        # check if we're already in the right status
        target_issue = self.get_issue(ticket)
        if target_issue:
            target_status = str(target_issue.fields.status)
            if target_status == status or target_status == "Won't Fix" or target_status == "Invalid":
                shlog.verbose(ticket + ' status ' + target_status + ' matches desired status ' + status + ', skipping...')
                return
            else:
                # retrieve transitions needed to get to desired status
                transitions = self.transitionX(target_status, status)
                for stat in transitions[1:]:
                    shlog.verbose('Posting status ' + stat + ' to ticket ' + ticket)
                    self.jira.transition_issue(ticket, transition=stat)
        else:
            return


    def create_jira_subtask(self,parent,summary,description,assignee,spoints=None,team=None):
        try:
            parent_issue = self.jira.issue(parent)
        except:
            warning= 'Parent issue %s does not exist!' % parent
            print(warning)
            sys.exit()

        if assignee is None:
            assignee = self.user

        if 'ncsa' in self.server.lower():
            subtask_dict = {'project': {'key': parent_issue.fields.project.key},
                            'summary': summary,
                            # change the issue type if needed
                            'issuetype': {'name': 'Story'},
                            'description': description,
                            'customfield_10536': parent_issue.key,  # this is the epic link
                            'reporter': {'name': assignee},
                            'customfield_10532': spoints
                            }
        if 'lsst' in self.server.lower():
            subtask_dict = {'project':{'key':parent_issue.fields.project.key},
                            'summary': summary,
                            # change the issue type if needed
                            'issuetype':{'name':'Story'},
                            'description': description,
                            'customfield_10206': parent_issue.key, # this is the epic link
                            'reporter':{'name': assignee},
                            'customfield_10202': spoints,
                            'customfield_10502': {"value": team}  # TODO: needs testing
                            }
        subtask = self.jira.create_issue(fields=subtask_dict)
        return subtask.key

    def create_jira_ticket(self,project,summary,description,assignee, wbs=None, start=None, due=None, spoints=None,
                           team=None):

        if assignee is None:
            assignee = self.user

        if 'ncsa' in self.server.lower():
            ticket_dict = {'project': {'key': project},
                           'customfield_10537': summary,
                           # THIS MIGHT (READ: DOES 100%) CHANGE IN DIFFERENT JIRA INSTANCES
                           'summary': summary,
                           'issuetype': {'name': 'Epic'},
                           'description': description,
                           'reporter': {'name': assignee}, # this works okay!
                           # 'customfield_13234': wbs,
                           'customfield_10630': start.strftime("%Y-%m-%d"),
                           'customfield_11930': due.strftime("%Y-%m-%d"),
                           'customfield_10532': spoints
                           }
        if 'lsst' in self.server.lower():
            ticket_dict = {'project':{'key':project},
                           'customfield_10207': summary,  # THIS MIGHT (READ: DOES 100%) CHANGE IN DIFFERENT JIRA INSTANCES
                           'summary': summary,
                           'issuetype':{'name':'Epic'},
                           'description': description,
                           'reporter':{'name': assignee},
                           'customfield_10500': wbs,
                           'customfield_11303': start.strftime("%Y-%m-%d"),
                           'customfield_11304': due.strftime("%Y-%m-%d"),
                           'customfield_10202': spoints,
                           'customfield_10502': {"value": team}  # TODO: needs testing
                           }
        ticket = self.jira.create_issue(fields=ticket_dict)
        return ticket.key

    def add_jira_comment(self,issue,comment):
        self.jira.add_comment(issue,comment)

    def list_links(self,issue):
        return self.jira.remote_links(issue)

    def add_external_link(self,issue,link,title=None):
        if not title:
            title = issue
        self.jira.add_simple_link(issue, {'url':link,'title':title})

    def check_if_unstarted(self,project,issue):
        # statuses equivalent to "Not Started"
        if 'ncsa' in self.server.lower():
            jql = 'project = "%s" and id = "%s" and (status = "To Do" or status = "Open")' % (project, issue)
        if 'lsst' in self.server.lower():
            jql = 'project = "%s" and id = "%s" and status = "To Do"' % (project, issue)
        shlog.verbose('JQL: ' + jql)
        try:
            count = len(self.jira.search_issues(jql))
        except jira.exceptions.JIRAError:
            # see:
            # https://jira.atlassian.com/browse/JRASERVER-23287?focusedCommentId=220596&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-220596
            count = 0
        if count > 0:
            return True
        else:
            return False

    def check_if_open(self,project,issue):
        # statuses equivalent to "In Progress"
        if 'ncsa' in self.server.lower():
            jql = 'project = "%s" and id = "%s" and (status = "Reopened" or status = "System Change Control" ' \
                  'or status = "In Progress" or status = "Blocked" or status = "Waiting on User" ' \
                  'or status = "Sleeping")' % (project, issue)
        if 'lsst' in self.server.lower():
            jql = 'project = "%s" and id = "%s" and (status = "In Progress" or status = "In Review" ' \
                  'or status = "Reviewed")' % (project, issue)
        shlog.verbose('JQL: ' + jql)
        try:
            count = len(self.jira.search_issues(jql))
        except jira.exceptions.JIRAError:
            # see:
            # https://jira.atlassian.com/browse/JRASERVER-23287?focusedCommentId=220596&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-220596
            count = 0
        if count > 0:
            return True
        else:
            return False

    def check_if_complete(self,project,issue):
        # statuses equivalent to "Completed"
        if 'ncsa' in self.server.lower():
            jql = 'project = "%s" and id = "%s" and (status = "Closed" or status = "Resolved")' % (project, issue)
        if 'lsst' in self.server.lower():
            jql = """project = "%s" and id = "%s" and (status = "Done" or status = "Won't Fix")""" % (project, issue)
        shlog.verbose('JQL: ' + jql)
        try:
            count = len(self.jira.search_issues(jql))
        except jira.exceptions.JIRAError:
            # see:
            # https://jira.atlassian.com/browse/JRASERVER-23287?focusedCommentId=220596&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-220596
            count = 0
        if count > 0:
            return True
        else:
            return False

    def search_for_user(self, email, name):
        users_raw = self.jira.search_users(email, maxResults=1000)
        users = []
        # remove test users
        for user in users_raw:
            if not ('test' in user.displayName.lower() or 'test' in user.emailAddress.lower()
                    or 'u829' in user.displayName.lower() or 'databot' in user.displayName.lower()):
                users.append(user)
        # fallback for different email edge cases
        if len(users) == 0:
            name = name.replace(',', '')
            users_raw = self.jira.search_users(name)
            for user in users_raw:
                if not ('test' in user.displayName.lower() or 'test' in user.emailAddress.lower()
                        or 'u829' in user.displayName.lower() or 'databot' in user.displayName.lower()):
                    users.append(user)
        return users



