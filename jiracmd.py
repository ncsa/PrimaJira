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
        jira=JIRA(options={'server':jiraserver},basic_auth=(jirauser,jirapasswd))
        self.jira = jira
        self.server = jiraserver
        self.user = jirauser
        self.project = jiraproject
        shlog.verbose('JIRA connection will use:\nServer: ' + jiraserver +
                      '\nUser: ' + jirauser + '\nPass: ' + '*'*len(jirapasswd) + '\nProject: ' + jiraproject)

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
        issue_info = self.jira.issue(key)
        return issue_info

    def create_jira_subtask(self,parent,summary,description,assignee,spoints=None,team=None):
        try:
            parent_issue = self.jira.issue(parent)
        except:
            warning= 'Parent issue %s does not exist!' % parent
            print(warning)
            sys.exit()

        if 'ncsa' in self.server.lower():
            subtask_dict = {'project': {'key': parent_issue.fields.project.key},
                            'summary': summary,
                            # change the issue type if needed
                            'issuetype': {'name': 'Story'},
                            'description': description,
                            'customfield_10536': parent_issue.key,  # this is the epic link
                            'assignee': {'name': assignee},
                            'customfield_10532': spoints
                            }
        if 'lsst' in self.server.lower():
            subtask_dict = {'project':{'key':parent_issue.fields.project.key},
                            'summary': summary,
                            # change the issue type if needed
                            'issuetype':{'name':'Story'},
                            'description': description,
                            'customfield_10206': parent_issue.key, # this is the epic link
                            'assignee':{'name': assignee},
                            'customfield_10202': spoints,
                            'customfield_10502': team  # TODO: needs testing
                            }
        subtask = self.jira.create_issue(fields=subtask_dict)
        return subtask.key

    def create_jira_ticket(self,project,summary,description,assignee, wbs=None, start=None, due=None, spoints=None,
                           team=None):
        if 'ncsa' in self.server.lower():
            ticket_dict = {'project': {'key': project},
                           'customfield_10537': summary,
                           # THIS MIGHT (READ: DOES 100%) CHANGE IN DIFFERENT JIRA INSTANCES
                           'summary': summary,
                           'issuetype': {'name': 'Epic'},
                           'description': description,
                           'assignee': {'name': assignee}, # this works okay!
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
                           'assignee':{'name': None}, # too many different emails
                           'customfield_10500': wbs,
                           'customfield_11303': start.strftime("%Y-%m-%d"),
                           'customfield_11304': due.strftime("%Y-%m-%d"),
                           'customfield_10202': spoints,
                           'customfield_10502': team  # TODO: needs testing
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
            jql = 'project = "%s" and id = "%s" and status = "Done"' % (project, issue)
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

    def search_for_user(self, email):
        users = self.jira.search_users(email)
        return users



