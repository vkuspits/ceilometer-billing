__author__ = "Services team"

import ceilometerclient.client
import argparse
import os
import datetime

dir_path = os.environ['PWD']+"/billing/"
parser = argparse.ArgumentParser()
parser.add_argument("--project_id", dest='project_id', help="write id of project, which statistics you want to get")
parser.add_argument("--project-all", default=False, action="store_true",
                    dest='project_all', help="Statistics of all cloud")
parser.add_argument("--username", default=os.environ.get('OS_USERNAME', 'admin'),
                    dest='username', help="name of the user")
parser.add_argument("--password", default=os.environ.get('OS_PASSWORD', 'admin'),
                    dest='password', help="password of the user")
parser.add_argument("--os_auth_url", default=os.environ.get('OS_AUTH_URL','http://10.21.2.3:5000/'),
                    dest='os_auth_url', help="write os_auth_url in format <http://hostname:5000/>")
parser.add_argument("--admin_project_name", default=os.environ.get('OS_PROJECT_NAME', 'admin'),
                    dest='admin_project_name', help="Specify name of admin project for auth")
parser.add_argument("--user_domain_id", default=os.environ.get('OS_DEFAULT_DOMAIN', 'default'),
                    dest='user_domain_id', help="Specify user domain id")
parser.add_argument("--project_domain_id", default=os.environ.get('OS_DEFAULT_DOMAIN', 'default'),
                    dest='project_domain_id', help="Specify project domain id")
parser.add_argument("--period_start",
                    dest='period_start', help="Time when period start in format <2017-01-12T00:00:00>")
parser.add_argument("--period_end",
                    dest='period_end', help="Time when period end in format <2017-01-13T00:00:00>")

args = parser.parse_args()

username = args.username
password = args.password
os_auth_url = args.os_auth_url
admin_project_name = args.admin_project_name
user_domain_id = args.user_domain_id
project_domain_id = args.project_domain_id
end_time = args.period_end
start_time = args.period_start

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
auth = v3.Password(auth_url=os_auth_url+"v3", username=username,
                   password=password, project_name=admin_project_name,
                   user_domain_id="default", project_domain_id="default")
sess = session.Session(auth=auth)
keystone = client.Client(session=sess)
cclient = ceilometerclient.client.get_client(2, username=username, password=password, project_name=admin_project_name,
                                             os_auth_url=os_auth_url)

if not os.path.exists(dir_path):
    os.makedirs(dir_path)

def volumes(project_id):
    volumes_hours = 0
    volume_samples = cclient.new_samples.list(q=[dict(field='project',op='eq',value=project_id),
             dict(field='meter',op='eq',value='volume.size')])

    for sample in volume_samples:
        if sample.metadata['status'] == u'deleting':
            time = datetime.datetime.strptime(sample.timestamp, '%Y-%m-%dT%H:%M:%S.%f') - datetime.datetime.strptime(
                sample.metadata['created_at'], '%Y-%m-%dT%H:%M:%S.%f')
            volumes_hours += sample.size * time.total_seconds() / 3600
            for delsample in volume_samples:
                if sample.resource_id == delsample.resource_id:
                    volume_samples.remove(delsample)

    for sample in volume_samples:
        if sample.metadata['status'] == u'available':
            time = datetime.datetime.now() - datetime.datetime.strptime(
                sample.metadata['created_at'], '%Y-%m-%dT%H:%M:%S.%f')
            volumes_hours += sample.size * time.total_seconds() / 3600
            for delsample in volume_samples:
                if sample.resource_id == delsample.resource_id:
                    volume_samples.remove(delsample)

    return volumes_hours


def estimation(meter):
    result = reduce(lambda a,b: a+b,map(lambda x: x.max*x.duration, meter))/3600
    return result

def billing(project_id):
    query = [dict(field='metadata.state',op='eq',value='active'), dict(field='timestamp',op='gt',value=start_time),
             dict(field="timestamp",op='lt',value=end_time), dict(field='project',op='eq',value=project_id)]

    vcpus = cclient.statistics.list('vcpus', q=query, period=86400, groupby='resource_id')
    rams = cclient.statistics.list('memory', q=query, period=86400, groupby='resource_id')
    disks_root = cclient.statistics.list('disk.root.size', q=query, period=86400, groupby='resource_id')
    disks_ephemeral = cclient.statistics.list('disk.ephemeral.size', q=query, period=86400, groupby='resource_id')

    vcpu_hour = estimation(vcpus)

    ram_hour_gb = estimation(rams)/1024 # By default ceilometer return memory meter in Mb

    disk_hour = estimation(disks_root) + estimation(disks_ephemeral)

    volume_hour = volumes(project_id)

    project_name = keystone.projects.get(project_id).name
    result = project_name+'\n'
    result += "VCPU hours: "+str(vcpu_hour)+"\n"+"RAM hours(Gb): "+str(ram_hour_gb)+"\n"+\
              "Disk hours(Gb): "+str(disk_hour)+"\n"+"Cinder volumes hours: "+ str(volume_hour)+"\n\n"
    return result

# If u want statistics of all projects
if args.project_all == True:
    project_list = keystone.projects.list()
    for project in project_list:
        if project.name != 'services':
            with open(dir_path+'ALL-'+str(end_time), 'a') as f:
                f.write(billing(project.id))
else:
    with open(dir_path+args.project_id+'-'+str(end_time), 'w') as f:
        f.write(billing(args.project_id))
