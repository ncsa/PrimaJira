# PrimaJira
Set of python scripts to sync Primavera WBS to Jira stories (tickets) and back

Features code originally developed by Michael Johnson and Donald Petravick:
* https://github.com/Michael-D-Johnson/pipebox/blob/master/python/pipebox/jira_utils.py
* https://github.com/Michael-D-Johnson/desdm-dash/blob/docker/app/jiracmd.py
* https://github.com/ncsa/archi_tools/blob/master/shlog.py

Uses Python 3.6+


## Use
Fill out the fields specified in *login_sample* and rename the file to *login*. Check the activities to be exported in NCSA's Primavera. Run *main.py*. 

> python main.py

The tool will take it from there.

## activity_complete.py
Goes through activities, finds their corresponding Epics and checks the Started/Finished checkboxes depending on the Epics' completion.

## diff.py
Compares Primavera and JIRA instances specified in the *login* file for inconsistencies, alerts the user and suggests further action.

## excel_to_primavera.py
Creates Activities and Steps within them from an excel file named input.xlsx

## jira_lync.py
Goes through Activities and their Steps, gathering their ticket records. Then, it will create records in the NCSA JIRA about corresponding tickets in the LSST JIRA.
