import xml.etree.ElementTree as ET
import re
import os
import sys
import subprocess
from urllib2 import Request, urlopen
from urllib import urlencode
from json import load, dumps
from base64 import b64encode
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
import xml.dom.minidom as minidom

result_file = "testng-results.xml"
project_name = "C3OV_PRISM"
en_user = "U1VCUlJBOTpTaGl2YUA4NQ=="
baseURL = 'http://onejira-test.verizon.com'
projectURL = baseURL + '/rest/zapi/latest/util/project-list'
getCyclesURL = baseURL + '/rest/zapi/latest/cycle'
getExecutionsURL = baseURL + '/rest/zapi/latest/execution'
postExecutionsURL = baseURL + '/rest/zapi/latest/execution'
getissueURL = baseURL + '/rest/api/2/issue'
searchURL = baseURL + '/rest/api/2/search'
issueURL = baseURL + '/rest/api/2/issue'

def api_get(restURL, callName):
    req = Request(restURL)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Basic '+en_user)

    try:
        res = urlopen(req)
        code = res.getcode()
        jsonresp = load(res)
        #print ("Status "+str(code)+" \n")
    except:
        print ("Error executing " +  callName + " API call")
        sys.exit(1)
    return jsonresp

def api_post(restURL, postData, callName):
    values = dumps(postData)
    req = Request(restURL,values)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Basic '+en_user)

    try:       
       res = urlopen(req)
       code = res.getcode()
       jsonresp = load(res)
       #print ("Status "+str(code)+" \n")
    except:
        print ("Error executing " +  callName + " API call")
        sys.exit(1)
    return jsonresp

print ("Finding Automation Results from testng result file...")

result_methods={}
failure_string={}
tree=ET.parse(result_file)
root=tree.getroot()
print (root)
for test in root.getiterator('test'):
   result_methods[test.attrib['name']]=[]
   for cla in test.getiterator('class'):
      for meth in cla.getiterator('test-method'):
         result_methods[test.attrib['name']].append(meth.attrib['status'])
         if meth.attrib['status'] == "FAIL":
             failure_string[test.attrib['name']] = []
             for excep in meth.getiterator('exception'):
                 failure_string[test.attrib['name']].append(excep[0].text)

print (result_methods)
print (failure_string)

result={}
failed_tests=[]
for i in result_methods:
   if 'FAIL' in result_methods[i]:
     result[re.sub('_','-',i)]=2
     failed_tests.append(i)
   else:
     result[re.sub('_','-',i)]=1
     

print (result)

print ("Results File Parsed! Execution Status Saved!\n")

print ("Finding Project ID...")
response_project = api_get(projectURL, "Project")

for i in response_project["options"]:
    if i['label'] == project_name:
        projectId=i['value']
print (projectId)

print ("Finding Cycle ID...")
cycle_name = sys.argv[1]
cycleParams = {
     "projectId": projectId
}
cycleURL = getCyclesURL + "?" + urlencode(cycleParams)
response_cycle = api_get(cycleURL, "Cycle")

for i in response_cycle["-1"]:
    for key in i:
        if isinstance(i[key],dict) and i[key]["name"] == cycle_name:
            cycleId = key
print (cycleId)

print ("Grabbing Executions from Fetched Cycle...")

fetchExecutionParams = {
     "action": "expand",
     "cycleId": cycleId
}

getExecutionsURL = getExecutionsURL + '/?' + urlencode(fetchExecutionParams)
response_execution = api_get(getExecutionsURL, "Execution")

fetchedExecutions = response_execution['executions']
executionIdList = {}
for rs in fetchedExecutions:
   executionIdList[rs['issueKey']]=str(rs['id'])

print ("Fetched Executions Completed. Number of Execution Assignments Found: " + str(len(executionIdList)) + "\n")
print (executionIdList)

# ///// Quick Execute Based on Fetched Executions ///// # Quick execute based on the parsed results file earlier

print ("Updating Cycle Execution(s) Status with Automation Results...")

for x in executionIdList:
#   print (x)
   if x in result:
      status_data = {"status": result[x]}
      executeURL = postExecutionsURL + '/' + executionIdList[x] + '/quickExecute'
      api_post(executeURL, status_data, "Status Execute")

print ("Automation Cycle Updated with Execution Status")

jiracli = "atlassian-cli-4.5.0/jira.sh"

def create_issue(project, summary):
    create_data = {"fields": {"project":{"id": project},"summary": summary,"issuetype": { "name": "Bug"}}}
    response_create = api_post(issueURL, create_data, "Create Issue" )
    return response_create["key"]

def attach_file(issue, file_location):
    out = subprocess.Popen(['curl', '-X', 'POST', '-H', "X-Atlassian-Token: no-check", '-H', "Authorization:Basic "+en_user, '-F', "file=@"+file_location, issueURL+'/'+issue+'/attachments'],stdout=subprocess.PIPE)
    return out.stdout.read()

def link_issue(issue1, issue2):

    out = subprocess.Popen([jiracli, '--action', 'linkIssue', '--issue', issue1, '--toIssue', issue2, '--link', 'relates to'],stdout=subprocess.PIPE)

    return out.stdout.read()

def search_issue(project, linked_issue):
    search_url = issueURL+"/"+linked_issue+"?fields=issuelinks"
    response_search = api_get(search_url, "Search")
    linked_issues=[]
    if len(response_search["fields"]["issuelinks"]) > 0:
        for i in response_search["fields"]["issuelinks"]:
            try:
                linked_issues.append(i["outwardIssue"]["key"])
            except:
                linked_issues.append(i["inwardIssue"]["key"])
    else:
        return linked_issues
    open_issues=[]
    for issue in linked_issues:
        status_url = issueURL+"/"+issue+"?fields=status"
        response_status = api_get(status_url, "Status")
        if response_status["fields"]["status"]["name"] != "Closed":
            open_issues.append(issue)
    return open_issues
                
def update_issue(issue, comment):
    updateURL = issueURL+"/"+issue+"/comment"
    print (updateURL)
    update_data = {"body": comment}
    print (update_data)
    response_update = api_post(updateURL, update_data, "Update Issue" )
    return response_update 
 
def close_issue(issue):

    out = subprocess.Popen([jiracli, '--action', 'transitionIssue', '--issue', issue, '--transition', "Close Issue", '--comment', "Closing the issue as the test case passed on test cycle "+cycle_name],stdout=subprocess.PIPE)

    return out.stdout.read()

issues_created=[]
issues_updated=[]
issues_closed=[]

for i in result:

    if result[i] == 1:

        cli_out = search_issue(project_name, i)

        print (cli_out)

        if len(cli_out) != 0:

            for j in cli_out:
                print j
                print (close_issue(j))
                issues_closed.append(j)

    elif result[i] == 2:

        cli_out = search_issue(project_name, i)

        print (cli_out)

        if len(cli_out) != 0:

            for j in cli_out:
                update_issue(j, failure_string[i][0].split("\n")[1] )
                issues_updated.append(j)
                file_out = os.popen("ls reports/ScreenShots/*"+i+"*.png")
                file_name = file_out.read().split('\n')[0]
                if file_name != '':
                    attach_file(j, file_name)

        else:

            cli_out = create_issue(projectId, failure_string[i][0].split("\n")[1] )
            issues_created.append(cli_out)

            file_out = os.popen("ls reports/ScreenShots/*"+i+"*.png")

            file_name = file_out.read().split('\n')[0]
            if file_name != '':
                attach_file(cli_out, file_name)
            link_issue(i,cli_out)
                    

f=open('testng-results.xml')
lines=f.readlines()
result = lines[1].split(" ")

email_file = open("email.txt",'w')
email_file.write("================================================\n")
email_file.write("Total number of test cases executed "+result[3]+"\n")
email_file.write("No of test cases "+result[4].split('>')[0]+"\n")
email_file.write("No of test cases "+result[2]+"\n")
email_file.write("No of test cases "+result[1]+"\n")
email_file.write("================================================\n")
email_file.write("Number of issue created = "+str(len(issues_created))+"\n")
email_file.write(str(issues_created)+"\n")
email_file.write("Number of issue updated = "+str(len(issues_updated))+"\n")
email_file.write(str(issues_updated)+"\n")
email_file.write("Number of issue closed = "+str(len(issues_closed))+"\n")
email_file.write(str(issues_closed)+"\n")
email_file.write("================================================\n")
email_file.close()

print ("Total number of test cases executed "+result[3])
print ("No of test cases "+result[4].split('>')[0])
print ("No of test cases "+result[2])
print ("No of test cases "+result[1])
print ("================================================")
print ("Number of issue created = "+str(len(issues_created)))
print (str(issues_created))
print ("Number of issue updated = "+str(len(issues_updated)))
print (str(issues_updated))
print ("Number of issue closed = "+str(len(issues_closed)))
print (str(issues_closed))

