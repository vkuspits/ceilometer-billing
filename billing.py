__author__ = "Services team"

import ceilometerclient.client
import argparse
import os

dir_path = os.environ['PWD']+"/billing/"
parser = argparse.ArgumentParser()
parser.add_argument("project", help="write id of project, which statistics you want to get")
parser.add_argument("--username", default=os.environ.get('OS_USERNAME', 'admin'),
                    dest='username', help="name of the user")
parser.add_argument("--password", default=os.environ.get('OS_PASSWORD', 'admin'),
                    dest='password', help="password of the user")
parser.add_argument("--os_auth_url", default=os.environ.get('OS_AUTH_URL','http://10.21.2.3:5000/'),
                    dest='os_auth_url', help="write os_auth_url in format <http://hostname:5000/>")
parser.add_argument("--peroid_start",
                    dest='period_start', help="Time when period start in format <2017-01-12T00:00:00>")
parser.add_argument("--period_end",
                    dest='period_end', help="Time when period end in format <2017-01-13T00:00:00>")
parser.add_argument("--project-all", default=False, action="store_true",
                    dest='project_all', help="Statistics of all cloud")
args = parser.parse_args()

username = args.username
password = args.password
os_auth_url = args.os_auth_url

end_time = args.period_end
start_time = args.period_start

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
auth = v3.Password(auth_url=os_auth_url+"v3", username=username,
                   password=password, project_name=os.environ.get('OS_PROJECT_NAME', 'admin'),
                   user_domain_id="default", project_domain_id="default")
sess = session.Session(auth=auth)
keystone = client.Client(session=sess)

def estimation(meter):
    result = reduce(lambda a,b: a+b,map(lambda x: x.max*x.duration, meter))/3600
    return result

def billing(project_id):
    cclient = ceilometerclient.client.get_client(2, username=username, password=password, tenant_id=project_id,
                                             os_auth_url=os_auth_url)
    query = [dict(field='metadata.state',op='eq',value='active'), dict(field='timestamp',op='gt',value=start_time),
             dict(field="timestamp",op='lt',value=end_time)]

    vcpus = cclient.statistics.list('vcpus', q=query, period=86400, groupby='resource_id')
    rams = cclient.statistics.list('memory', q=query, period=86400, groupby='resource_id')
    disks = cclient.statistics.list('disk.root.size', q=query, period=86400, groupby='resource_id')

    vcpu_hour = estimation(vcpus)

    ram_hour_gb = estimation(rams)/1024 # By default ceilometer return memory meter in Mb

    disk_hour = estimation(disks)

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    project_name = keystone.projects.get(project_id).name
    result = project_name+'\n'
    result += "VCPU per hour: "+str(vcpu_hour)+"\n"+"RAM per hour(Gb): "+str(ram_hour_gb)+"\n"+\
              "Disk per hour(Gb): "+str(disk_hour)+"\n\n"
    return result

# If u want statistics of all projects
if args.project_all == True:
    project_list = keystone.projects.list()
    for project in project_list:
        if project.name != 'services':
            with open(dir_path+'ALL-'+str(end_time), 'a') as f:
                f.write(billing(project.id))
else:
    with open(dir_path+args.project+'-'+str(end_time), 'w') as f:
        f.write(billing(args.project))
