import os
import re
import sys
import time
from json import load, dumps
from urllib2 import Request, urlopen
from urllib import urlencode
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
import xml.dom.minidom as minidom

project_name = "KOIG_MSOLV"
if sys.argv[1] == "None":
    cycle_name="Regression-Auto-"+time.strftime("%Y/%m/%d-%H:%M:%S")
else:
    cycle_name=sys.argv[1]
property_file = open("env.properties",'w')
property_file.write("cycle_name="+cycle_name)
property_file.close()
en_user = "U1VCUlJBOTpNYXRyaXhAODU="
baseURL = 'http://onejira-test.verizon.com'
projectURL = baseURL + '/rest/zapi/latest/util/project-list'
cycleURL = baseURL + '/rest/zapi/latest/cycle'
execURL = baseURL + '/rest/zapi/latest/execution'
issuesURL = baseURL + '/rest/zapi/latest/issues'
testtocycleURL = baseURL + '/rest/zapi/latest/execution/addTestsToCycle'
issueURL = baseURL + '/rest/api/2/issue'
searchURL = baseURL + '/rest/api/2/search'

def api_get(restURL, callName):
    req = Request(restURL)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Basic '+en_user)

    try:
        res = urlopen(req)
        code = res.getcode()
        jsonresp = load(res)
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
        print ("Status "+str(code)+" \n")
    except:
        print ("Error executing " +  callName + " API call")
        sys.exit(1)
    return jsonresp

def f(x):
    if "-" in x:
	    num=x.split("-",2)[1]
    elif "_" in x:
	    num=x.split("_",2)[1]
    if num.isdigit():
        return int(num)
    return x

print ("Finding Project ID...")
response_project = api_get(projectURL, "Project")

for i in response_project["options"]:
    if i['label'] == project_name:
        projectId=i['value']
        print (projectId)

if sys.argv[1] == "None":
    print ("Creating Test Cycle in Jira...")
    cycle_data = {"name":cycle_name,"projectId":projectId,"versionId":"-1"}
    response_cycle = api_post(cycleURL, cycle_data, "Cycle")
    cycleId = response_cycle['id']
    print (cycleId)

    print ("Finding Test cases in the project...")
    test_names=[]
    class_names=[]
    search_data = {"jql":"project = "+project_name+" & type = Test", "maxResults":250, "fields":["id","key","status"]}
    response_search = api_post(searchURL, search_data, "Search")
    for issue in (response_search['issues']):
        if issue["fields"]["status"]["name"] != "Closed":
            test_names.append(issue['key'])
            class_names.append(re.sub('-','_',issue['key']))
	

    test_names = sorted(set(test_names), key=f)
    class_names = sorted(set(class_names), key=f)


    print (test_names)
    print (class_names)

    print ("Adding Test cases to Test Cycle in Jira...")
    testtocycle_data = {"issues":test_names,"versionId":-1,"cycleId":cycleId,"projectId":projectId}
    response_testtocycle = api_post(testtocycleURL, testtocycle_data, "Add test to cycle")
    print (response_testtocycle)

else:
    print ("Finding Cycle ID...")
    cycleValues = {
     "projectId": projectId
     }
    cycleURL = cycleURL + "?" + urlencode(cycleValues)
    response_cycle = api_get(cycleURL, "Cycle")

    for i in response_cycle["-1"]:
        for key in i:
            if isinstance(i[key],dict) and i[key]["name"] == cycle_name:
                cycleId = key
                print (cycleId)

    print ("Finding Test cases...")
    test_names=[]
    class_names=[]
    execValues = {
     "cycleId": cycleId
     }
    execURL = execURL + "?" + urlencode(execValues)
    response_exec = api_get(execURL, "Execution")

    for i in range(len(response_exec["executions"])):
        issue=response_exec["executions"][i]["issueKey"]
        test_names.append(issue)
        class_names.append(re.sub('-','_',issue))

    test_names.reverse()
    class_names.reverse()
    print (test_names)
    print (class_names)

print ("Finding Class path from test case label...")
test_labels={}
for test in test_names:
    loopURL = issueURL + "/" + test
    response_issue = api_get(loopURL, "Issue")
    test_labels[test] = response_issue["fields"]["labels"]
print (test_labels)

print ("Generating testng xml file...")
root = Element('suite', name=cycle_name, parallel="tests", threadcount="1")
child1 = SubElement(root, "listeners")
c1 = SubElement(child1, 'listener', classname="utility.MsolvListener")
for i in range(len(test_names)):
    child = SubElement(root, "test", name=test_names[i])
    node1_1 = SubElement(child, "parameter", name="testCaseId", value=test_names[i])
    node1_2 = SubElement(child, "parameter", name="BrowserType", value="IE")
    node1_3 = SubElement(child, "parameter", name="BrowserType1", value="firefox")
    node2 = SubElement(child, "classes")
    if test_labels[test] != []:
        node3 = SubElement(node2, 'class', name="msol."+test_labels[test_names[i]][0]+"."+class_names[i])
    else:
        print ("Found a test case without label in JIRA. Please add class name as label.")
        sys.exit(1)

rough_string = tostring(root, 'utf-8')
reparsed = minidom.parseString(rough_string)
pretty_out = reparsed.toprettyxml(indent="\t")

with open("first.xml", "w") as f1:
    f1.write(pretty_out)
f1.close()

with open("first.xml") as f2:
    with open("testng.xml", "w") as f3:
        for line in f2:
            if "classname" in line:
                output_line = line.replace("classname", "class-name")
            elif "threadcount" in line:
                output_line = line.replace("threadcount", "thread-count")
            else:
                output_line = line
            print (output_line)
            f3.write(output_line)

f2.close()
f3.close()

