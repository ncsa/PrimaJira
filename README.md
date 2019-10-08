# PrimaJira
Set of python scripts to sync Primavera WBS to Jira stories (tickets) and back

Features code originally developed by Michael Johnson and Donald Petravick:
* https://github.com/Michael-D-Johnson/pipebox/blob/master/python/pipebox/jira_utils.py
* https://github.com/Michael-D-Johnson/desdm-dash/blob/docker/app/jiracmd.py
* https://github.com/ncsa/archi_tools/blob/master/shlog.py

Uses Python 2.7+

## Use
Fill out the fields specified in *login_sample* and rename the file to *login*. Check the activities to be exported in NCSA's Primavera. Run *main.py*. 

> python main.py

The tool will take it from there.

## diff.py
diff.py will compare Primavera and JIRA instances specified in the *login* file for inconsistencies, alert the user and suggest further action.
