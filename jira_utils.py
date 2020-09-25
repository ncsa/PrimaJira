# jira_utils.py originally developed by Michael D Johnson
# https://github.com/Michael-D-Johnson/pipebox/blob/master/python/pipebox/jira_utils.py

import os
import time
import configparser
import jiracmd

def get_con(jira_section, retry = 3,sleep = 15):
    num_retries = 0
    while num_retries < retry:
        try:
            return jiracmd.Jira(jira_section)
        except:
            num_retries += 1
            time.sleep(sleep)
            print("JIRA Connection Error...Retry %s" % num_retries)

def get_jira_user(section='jira-desdm',services_file=None):
    Config = configparser.ConfigParser()
    if not services_file:
        services_file = os.path.join(os.environ['HOME'],'.desservices.ini')
    try:
        Config.read(services_file)
        jirauser = Config.get(section,'user')
        return jirauser
    except:
        return os.environ['USER']


def use_existing_ticket(con,dict):
    """Looks to see if JIRA ticket exists. If it does it will use it instead
       of creating a new ticket. Returns reqnum,jira_id"""
    Config = configparser.ConfigParser()
    Config.read('login')
    jiraproject = Config.get('jira-section', 'project')
    issues,count = con.search_for_issue(dict['summary'])
    if count != 0:
        # If the epic with this exact name exists, we can just use it
        reqnum = str(issues[0].key).split('-')[1]
        jira_id = issues[0].key
        return (reqnum,jira_id)
    else:
        new_story = str(con.create_jira_ticket(jiraproject, dict['summary'], dict['description'], dict['jira_user'],
                                               wbs=dict['wbs'], start=dict['start'], due=dict['due'],
                                               spoints=dict['spoints'], team=dict['team']))
        reqnum = new_story.split('-')[1]
        jira_id = new_story
        return (reqnum,jira_id)

def create_subticket(con,dict):
    """Takes a JIRA connection object and a dictionary and creates a
       subticket. Returns the reqnum,jira_id"""
    issues, count = con.search_for_issue(dict['summary'], parent=dict['parent'])
    if count != 0:
        # If a subticket with this exact name exists, we can just use it
        reqnum = str(issues[0].key).split('-')[1]
        jira_id = issues[0].key
        return (reqnum, jira_id)
    else:
        subticket = str(con.create_jira_subtask(dict['parent'],dict['summary'], dict['description'],
                                                dict['jira_user'], spoints=dict['spoints'], team=dict['team']))
        reqnum = subticket.split('-')[1]
        jira_id = subticket
        return (reqnum, jira_id)


def create_ticket(jira_section, jira_user, ticket=None, parent=None, summary=None, description=None, use_existing=False,
                  project=None, prima_code=None, WBS=None, start=None, due=None, spoints=None, team=None):
    """ Create a JIRA ticket for use in framework processing. If parent is specified,
    will create a subticket. If ticket is specified, will use that ticket. If no parent is specified,
    will create the ticket as a story. Parent and ticket
    should be specified as the number, e.g., 1515. Returns tuple (reqnum,jira_id):
    (1572,DM-1515)"""
    args_dict = {'jira_section':jira_section,'jira_user':jira_user,
                 'parent':parent,'ticket':ticket,'summary':summary,
                 'description':description,'use_existing':use_existing,
                 'project':project,'wbs':WBS,'start':start,'due':due,'spoints':spoints,'team':team}
    if parent and ticket:
        pass
    else:
        con = get_con(jira_section)
    if not summary:
        args_dict['summary'] = 'No summary provided!'
    if not description:
        args_dict['description'] = 'No description provided!'
    args_dict['description'] += '\n\nThis ticket had been created automatically\nPrimavera ID: ' + str(prima_code)
    if parent and ticket:
        ticket = project + '-' + ticket
        parent = project + '-' + parent
        args_dict['parent'],args_dict['ticket'] = parent,ticket
        # Return what was given
        return (ticket.split('-')[1],parent)
    if ticket and not parent:
        ticket = project + '-' + ticket
        args_dict['ticket'] = ticket
        reqnum = ticket.split('-')[1] 

        # Use ticket specified and find parent key
        try:
            jira_id = con.get_issue(ticket).fields.parent.key
        except:
            jira_id = reqnum
        return (reqnum,jira_id)

    if parent and not ticket:
        parent = project + '-' + parent
        args_dict['parent'] = parent

        # Create subticket under specified parent ticket
        reqnum,jira_id = create_subticket(con,args_dict)
        return (reqnum,jira_id)
    if not ticket and not parent:
        reqnum, jira_id = use_existing_ticket(con, args_dict)
        return (reqnum, jira_id)
        # parent_summary = args_dict['summary']
        # parent_description = description
        # is_parent = con.search_for_parent('DM',parent_summary)
        # if is_parent[1] == 0:
        #     # If no parent ticket found create one
        #     parent = str(con.create_jira_ticket('DM',parent_summary,parent_description,jira_user))
        #     args_dict['parent'] = parent
        #     if use_existing:
        #         reqnum,jira_id = use_existing_ticket(con,args_dict)
        #         return (reqnum,jira_id)
        #     else:
        #         reqnum,jira_id = create_subticket(con,args_dict)
        #         return (reqnum,jira_id)
        # else:
        #     # Take found parent and create subticket
        #     parent = str(is_parent[0][0].key)
        #     args_dict['parent'] = parent
        #     if use_existing:
        #         reqnum,jira_id = use_existing_ticket(con,args_dict)
        #         return (reqnum,jira_id)
        #     else:
        #         reqnum,jira_id = create_subticket(con,args_dict)
        #         return (reqnum,jira_id)

def link_second_jira(con,local_issue,remote_issue,remote_server):
    """Check if the remote issue had been linked, and if not, create a new link"""
    link_list = con.list_links(local_issue)
    already_linked = False
    for link in link_list:
        if remote_issue in link.object.url:
            already_linked = True
    if not already_linked:
        url = remote_server + '/browse/' + remote_issue
        con.add_external_link(local_issue, url, remote_issue)