import openpyxl
import configparser
import main as m

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
tool_fixer = tool_dict['fix']
if tool_fixer.lower() in ['true', '1', 't', 'y', 'yes', 'yeah', 'yup', 'certainly', 'uh-huh']:
    tool_fixer = True
else:
    tool_fixer = False


# preload file and worksheet
workbook = openpyxl.load_workbook('input.xlsx', data_only=True)
acts_sheet = workbook.get_sheet_by_name('Epic Suggestions')
steps_sheet = workbook.get_sheet_by_name('TaskStory Suggestion')

# go through activity entries in the file
# because max_row method counts rows even after they've been wiped, it's time to go back to the old VBA ways...
i = 2
while True:
    import_check = acts_sheet.cell(row=i, column=1).value
    if import_check == 'TRUE' or import_check == True:
        continue  # skip TRUE items
    if import_check == '' or import_check == None or import_check == ' ':
        break  # stop execution
    act_name = acts_sheet.cell(row=i, column=2).value
    # Activity creation code
    request_data = {'Activity': {'Name': act_name,
                                 'AtCompletionDuration': 0,
                                 'CalendarObjectId': 638,  # NCSA Standard with Holidays, ok to hardcode
                                 'ProjectObjectId': m.actual_baseline(primaserver, primauser, primapasswd),
                                 # 408 is the one currently active
                                 'ProjectId': 'LSST MREFC',
                                 'WBSObjectId': 4597,
                                 'WBSPath': 'LSST MREFC.MREFC.LSST Construction.Test WBS'# the big dump
                                 }}
    synched = m.soap_request(request_data, primaserver, 'ActivityService', 'CreateActivities', primauser, primapasswd)
    created_activity = synched[0]
    print(created_activity)
    # go through all steps and find relevant ones
    r = 2
    while True:
        step_name = steps_sheet.cell(row=r, column=2).value
        if step_name == '' or step_name == None or step_name == ' ':
            break
        if steps_sheet.cell(row=r, column=1).value == act_name:
            step_desc = steps_sheet.cell(row=r, column=7).value
            try:
                step_pts = int(steps_sheet.cell(row=r, column=5).value)/4
            except TypeError:
                step_pts = 0
            # Step creation code
            request_data = {'ActivityStep': {'ActivityObjectId': created_activity,
                                         'Description': step_desc,
                                         'Name': step_name,
                                         'Weight': step_pts}}
            synched = m.soap_request(request_data, primaserver, 'ActivityStepService', 'CreateActivitySteps', primauser, primapasswd)
            # created_activity = synched[0]
        r += 1
    i += 1

# 41186
