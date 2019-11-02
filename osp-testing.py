import argparse
import os
import sys
import configparser
import time
from prettytable import PrettyTable
from keystoneauth1 import identity
from keystoneauth1 import session
from neutronclient.v2_0 import client as neutron_client
from glanceclient import Client as glance_client
from novaclient import client as nova_client
from cinderclient import client as cinder_client

confparser = configparser.ConfigParser()
confparser.read('overcloud_conf.ini')
test_data = {}
component = PrettyTable()
component.field_names= ['Operation', 'Status', 'Result/ID']


def val_overcloud_conf(service, operation, client):
    if service == "neutron":
        if confparser.has_section('nova') and not confparser.has_option('glance', 'image_absolute_path'):
            raise Exception("Nova is true but image is not specified in 'Glance' section of overcloud_config.ini")
        if confparser.has_option('neutron', 'external-network-id'):
            if not (client.show_network(confparser.get('neutron', 'external-network-id'))['network']
            ['router:external']):
                raise Exception("Provided external network({}) is not external/public/floating".format
                                (confparser.get('neutron', 'external-network-id')))
        else:
            component.add_row([operation, "INFO", "'external-network-id' is not defined in [neutron] section of "
                                                  "overcloud_conf.ini. \nFloating IP will not be created. Router will "
                                                  "be created without default gateway."])

    if service == "glance":
        if confparser.has_option('glance', 'image_absolute_path'):
            full_path = os.path.expanduser(confparser.get('glance', 'image_absolute_path'))
            if not os.path.exists(full_path):
                raise Exception("Invalid image path: {}".format(confparser.get('glance', 'image_absolute_path')))
        else:
            raise Exception("'image_absolute_path' is not defiened in overcloud_conf.ini")

    if service == "nova":
        if not confparser.has_section('glance'):
            raise Exception("Nova is true but Glance section is not defined in overcloud_config.ini")

    if service == "cinder":
        pass


def task_timeout(service):
    if confparser.has_option(service, 'timeout'):
        return int(confparser.get(service, 'timeout'))
    else:
        return 60


def overcloud_auth():
    try:
        username = os.environ['OS_USERNAME']
        password = os.environ['OS_PASSWORD']
        project_name = os.environ['OS_PROJECT_NAME']
        project_domain_name = os.environ['OS_PROJECT_DOMAIN_NAME']
        user_domain_name = os.environ['OS_USER_DOMAIN_NAME']
        auth_url = os.environ['OS_AUTH_URL']
    except:
        sys.exit("ERROR: Please source overcloudrc to proceed further")

    auth = identity.Password(auth_url=auth_url,
                             username=username,
                             password=password,
                             project_name=project_name,
                             project_domain_name=project_domain_name,
                             user_domain_name=user_domain_name)
    return session.Session(auth=auth)


def create_network(args, neutron):
    network_data = {'name': "rax-test-network-"+str(args.ticket_id)}
    network = neutron.create_network({'network': network_data})
    test_data['network_id'] = network['network']['id']
    test_data['network_name'] = network['network']['name']


def create_subnet(args, network_id, neutron):
    subnet_data = {'network_id': network_id, 'name': "rax-test-subnet-"+str(args.ticket_id), 'ip_version': 4,
                   'cidr': '192.168.100.0/24'}
    subnet_id = neutron.create_subnet({'subnet': subnet_data})['subnet']['id']
    test_data['subnet_id'] = subnet_id


def create_router(args, neutron):
    router_data={'name': "rax-test-router-"+str(args.ticket_id)}
    router_id=neutron.create_router({'router': router_data})['router']['id']
    test_data['router_id'] = router_id


def set_router_gw(external_network_id, router_id, neutron):
    router_data = {
        'external_gateway_info': {
            "network_id": external_network_id,
            "enable_snat": True,
            "external_fixed_ips": [
                {
                    "subnet_id": neutron.show_network(external_network_id)['network']['subnets'][0]
                }
            ]
        }
    }

    neutron.update_router(router_id, {'router': router_data})


def add_subnet_r(router_id, subnet_id, neutron):
    neutron.add_interface_router(router_id, {'subnet_id': subnet_id})


def delete_neutron(neutron):
    try:
        operation = "Detach Subnet from Router"
        neutron.remove_interface_router(test_data['router_id'], {'subnet_id': test_data['subnet_id']})
        component.add_row([operation, "SUCCESS", "-"])
        operation = "Delete Router"
        neutron.delete_router(test_data['router_id'])
        component.add_row([operation, "SUCCESS", test_data['router_id']])
        test_data.pop('router_id')
        operation = "Delete Network"
        neutron.delete_network(test_data['network_id'])
        component.add_row([operation, "SUCCESS", test_data['network_id']])
        test_data.pop('network_id')
        test_data.pop('network_name')
        if confparser.has_option('neutron', 'external-network-id'):
            operation = "Delete Floating IP"
            neutron.delete_floatingip(test_data['floation_ip_id'])
            component.add_row([operation, "SUCCESS", test_data['floating_ip']])
            test_data.pop('floating_ip')
            test_data.pop('floation_ip_id')
    except Exception as e:
        component.add_row([operation, "FAILED", str(e)])


def create_floating_ip(external_network_id, neutron):
    floating = neutron.create_floatingip({'floatingip': {'floating_network_id':
                                                         external_network_id}})
    test_data['floating_ip'] = floating['floatingip']['floating_ip_address']
    test_data['floation_ip_id'] = floating['floatingip']['id']


def create_image(args, glance):
    ticket_id = args.ticket_id
    test_data['image_id'] = glance.images.create(name="rax-test-image-"+ticket_id, disk_format="qcow2",
                                                 container_format="bare").id
    full_path = os.path.expanduser(confparser.get('glance', 'image_absolute_path'))
    glance.images.upload(test_data['image_id'], open(full_path), 'rb')


def delete_image(glance, operation):
    glance.images.delete(test_data['image_id'])
    for i in glance.images.list():
        if i['id'] != test_data['image_id']:
            component.add_row([operation, "SUCCESS", test_data['image_id']])
            test_data.pop('image_id')
            return
        else:
            raise Exception("Something went wrong while deleting image: {}".format(test_data['image_id']))


def create_flavor(args, nova):
        flavor=nova.flavors.create("rax-test-flavor-"+args.ticket_id, 2048, 2, 10)
        test_data['flavor_id'] = str(flavor.id)


def delete_flavor(nova, operation):
    nova.flavors.delete(test_data['flavor_id'])
    component.add_row([operation, "SUCCESS", test_data['flavor_id']])
    test_data.pop('flavor_id')


def create_keypair(args, nova):
    keypair = nova.keypairs.create(name="rax-test-keypair-"+args.ticket_id)
    test_data['keypair_id'] = str(keypair.id)
    test_data['keypair_private_key'] = str(keypair.private_key)


def delete_keypair(nova, operation):
    nova.keypairs.delete(test_data['keypair_id'])
    component.add_row([operation, "SUCCESS", test_data['keypair_id']])
    test_data.pop('keypair_id')
    test_data.pop('keypair_private_key')


def create_instance(args, nova):
    instance = nova.servers.create("rax-test-instance-"+args.ticket_id, test_data['image_id'], test_data['flavor_id'],
                                   key_name=test_data['keypair_id'], nics=[{'net-id':test_data['network_id']}])
    test_data['instance_id'] = str(instance.id)


def delete_instance(nova, timeout):
    operation = "Delete instance"
    nova.servers.delete(test_data['instance_id'])
    while timeout > 0:
        if not nova.servers.findall(id=test_data['instance_id']):
            component.add_row([operation, "SUCCESS", test_data['instance_id']])
            break
        time.sleep(1)
        timeout -= 1
        if timeout == 0:
            component.add_row([operation, "Timed out", "-"])
            return


def create_volume(args, cinder):
    volume_type = None
    try:
        if confparser.has_section('cinder'):
            volume_type = confparser.get('cinder', 'volume_type')
    except configparser.NoOptionError:
        volume_type = None
    volume_id=cinder.volumes.create(10, name='rax-test-volume-'+args.ticket_id, volume_type=volume_type)
    test_data['volume_id'] = str(volume_id.id)


def delete_volume(cinder, operation):
    try:
        timeout = task_timeout('cinder')
        cinder.volumes.detach(test_data['volume_id'])
        cinder.volumes.delete(test_data['volume_id'])
        while timeout > 0:
            if not cinder.volumes.findall(id=test_data['volume_id']):
                component.add_row([operation, "SUCCESS", test_data['volume_id']])
                test_data.pop('volume_id')
                break
            time.sleep(1)
            timeout -= 1
            if timeout == 0:
                component.add_row([operation, "Timed out", "-"])
                return
    except Exception as e:
            component.add_row([operation, "FAILED", str(e)])


def attach_volume(cinder, operation, timeout):
    try:
        cinder.volumes.attach(test_data['volume_id'], test_data['instance_id'], "/dev/sdb")
        while timeout >0:
            if cinder.volumes.get(test_data['volume_id']).attachments[0]['server_id'] == test_data['instance_id']:
                component.add_row([operation, "SUCCESS", "-"])
                break
            time.sleep(1)
            timeout -= 1
            if timeout == 0:
                component.add_row([operation, "Timed out", "-"])
                return
    except Exception as e:
            component.add_row([operation, "FAILED", e])


def val_glance(args, glance):
    try:
        operation = "Create Image"
        create_image(args, glance)
        if glance.images.get(test_data['image_id'])['status'].lower() == 'active':
            component.add_row([operation, "SUCCESS", test_data['image_id']])
        else:
            raise Exception("Something went wrong while creating image: {}".format(test_data['image_id']))

        if not confparser.has_section('nova'):
            operation = "Delete Image"
            delete_image(glance, operation)
    except Exception as e:
            component.add_row([operation, "FAILED", e])


def val_nova(args, nova, neutron, glance, cinder, nova_timeout):
    try:
        for i in nova.services.findall():
            if str(i.state) == "down":
                operation = "Delete Image"
                delete_image(glance, operation)
                if confparser.has_section('neutron'):
                    delete_neutron(neutron)
                print("ERROR: Nova is down")
                os.system('openstack compute service list')
                return
        if "network_id" not in test_data.keys():
            val_neutron(args, neutron)
        if "image_id" not in test_data.keys():
            try:
                val_glance(args, glance)
            except:
                delete_neutron(neutron)
        operation = "Create Flavor"
        create_flavor(args, nova)
        while nova_timeout > 0:
            if 'flavor_id' in test_data:
                component.add_row([operation, 'SUCCESS', test_data['flavor_id']])
                break
            time.sleep(1)
            nova_timeout -= 1


        operation = "Create Keypair"
        create_keypair(args, nova)
        while nova_timeout > 0:
            if 'keypair_id' in test_data:
                component.add_row([operation, 'SUCCESS', test_data['keypair_id']])
                break
            time.sleep(1)
            nova_timeout -= 1

        if "volume_id" not in test_data.keys():
            val_cinder(args, cinder)

        operation = "Create Instance"
        create_instance(args, nova)
        while nova_timeout > 0:
            if nova.servers.get(test_data['instance_id']).status.lower() == "active":
                component.add_row([operation, "SUCCESS", test_data['instance_id']])
                if not confparser.has_option('nova', 'delete'):
                    f = open("rax-test-keypair-"+args.ticket_id, "w")
                    f.write(test_data['keypair_private_key'])
                    f.close()
                break
            time.sleep(1)
            nova_timeout -= 1
            if nova_timeout == 0:
                component.add_row([operation, "Timed out", "-"])
                return
        if test_data.has_key('floating_ip'):
            operation = "Assign Floating IP"
            f_ip_assigned = False
            os.system('openstack server add floating ip {} {}'.format(test_data['instance_id'],
                                                                      test_data['floating_ip']))
            while nova_timeout > 0:
                for i in nova.servers.ips(test_data['instance_id'])[test_data['network_name']]:
                    if i['addr'] == test_data['floating_ip']:
                        f_ip_assigned = True
                        component.add_row([operation, "SUCCESS", "-"])
                if f_ip_assigned:
                    break
                time.sleep(1)
                nova_timeout -= 1
                if nova_timeout == 0:
                    component.add_row([operation, "Timed out", "-"])
                    return
        if test_data.has_key('volume_id'):
            operation = "Attach volume to the instance"
            attach_volume(cinder, operation, nova_timeout)
        if confparser.has_option('nova', 'delete'):
            if str(confparser.get('nova', 'delete')).lower() == "true":
                if "volume_id" in test_data.keys():
	            operation = "Detach and delete the volume"
                    delete_volume(cinder, operation)
                operation = "Delete Instance"
                delete_instance(nova, nova_timeout)
                delete_neutron(neutron)
                operation = "Delete Image"
                delete_image(glance, operation)
                operation = "Delete Keypair"
                delete_keypair(nova, operation)
                operation = "Delete Flavor"
                delete_flavor(nova, operation)
    except Exception as e:
        component.add_row([operation, "FAILED", str(e)])


def val_neutron(args, neutron):
    try:
        operation = "Status of Neutron API"
        for i in neutron.list_agents()['agents']:
            if not i['alive']:
                print("ERROR: Neutron is down")
                os.system('openstack network agent list')
                return
        operation = "Create Network"
        create_network(args, neutron)
        if neutron.show_network(test_data['network_id'])['network']['status'].lower() == 'active':
            component.add_row([operation, "SUCCESS", test_data['network_id']])
        else:
            raise Exception("Something went wrong while creating network: {}".format(test_data['network_id']))
        operation = "Create Subnet"
        create_subnet(args, test_data['network_id'], neutron)
        component.add_row([operation, "SUCCESS", test_data['subnet_id']])
        operation = "Create Router"
        create_router(args, neutron)
        if neutron.show_router(test_data['router_id'])['router']['status'].lower() == 'active':
            component.add_row([operation, "SUCCESS", test_data['router_id']])
        else:
            raise Exception("Something went wrong while creating router: {}".format(test_data['router_id']))
        operation = "Attach subnet to router"
        add_subnet_r(test_data['router_id'], test_data['subnet_id'], neutron)
        component.add_row([operation, "SUCCESS", '-'])
        if confparser.has_option('neutron', 'external-network-id'):
            operation = "Set external GW to router"
            set_router_gw(confparser.get('neutron', 'external-network-id'), test_data['router_id'], neutron)
            component.add_row([operation, "SUCCESS", "-"])
            operation = "Create Floating IP"
            create_floating_ip(confparser.get('neutron', 'external-network-id'), neutron)
            component.add_row([operation, "SUCCESS", test_data['floating_ip']])
        if not confparser.has_section('nova'):
            operation = "Delete Neutron resources"
            delete_neutron(neutron)
    except Exception as e:
        component.add_row([operation, "FAILED", str(e)])
        return


def val_cinder(args, cinder):
    try:
        timeout = task_timeout('cinder')
        if confparser.has_section('cinder'):
            if confparser.has_option('cinder', 'check_service_status'):
                if str(confparser.get('cinder', 'check_service_status')) == 'true':
                    operation = "Status of Cinder API"
                    for i in cinder.services.list(binary='cinder-scheduler'):
                        if i.state == 'down':
                            print("ERROR: Cinder is down")
                            os.system('openstack volume service list')
                            return
        operation = "Create volume"
        create_volume(args, cinder)
        while timeout > 0:
            if cinder.volumes.get(test_data['volume_id']).status.lower() == 'available':
                component.add_row([operation, "SUCCESS", test_data['volume_id']])
                break
            time.sleep(1)
            timeout -= 1
            if timeout == 0:
                component.add_row([operation, "Timed out", "-"])
                return
        if not confparser.has_section('nova'):
            operation = "Delete cinder volume"
            delete_volume(cinder, operation)

    except Exception as e:
        component.add_row([operation, "FAILED", str(e)])
        return


def main():
    parser = argparse.ArgumentParser(description="Test RHOS components functionality")
    parser.add_argument("ticket_id",
                        help="Maintenance ticket ID / Random string")
    args = parser.parse_args()
    try:
        open('overcloud_conf.ini', "r")
        if confparser.has_section('neutron'):
            operation = "Neutron: Validating 'overcloud_conf.ini'"
            neutron = neutron_client.Client(session=overcloud_auth())
            val_overcloud_conf('neutron', operation, neutron)
            print("Neutron is true")
            val_neutron(args, neutron)

        if confparser.has_section('glance'):
            print("Glance is true")
            operation = "Glance: Validating 'overcloud_conf.ini'"
            glance = glance_client('2', session=overcloud_auth())
            val_overcloud_conf('glance', operation, glance)
            val_glance(args, glance)

        if confparser.has_section('cinder'):
            print("Cinder is true")
            operation = "Cinder: Validating 'overcloud_conf.ini'"
            cinder = cinder_client.Client("2", session=overcloud_auth())
            val_overcloud_conf('cinder', operation, cinder)
            val_cinder(args, cinder)

        if confparser.has_section('nova'):
            print("Nova is true")
            operation = "Nova: Validating 'overcloud_conf.ini'"
            nova = nova_client.Client('2', session=overcloud_auth())
            neutron = neutron_client.Client(session=overcloud_auth())
            glance = glance_client('2', session=overcloud_auth())
            cinder = cinder_client.Client("2", session=overcloud_auth())
            val_overcloud_conf('nova', operation, nova)
            timeout = task_timeout('nova')
            val_nova(args, nova, neutron, glance, cinder, timeout)

    except IOError:
        sys.exit('ERROR: Overcloud configuration file {}/overcloud_conf.ini does not exist'.format(os.getcwd()))
    except Exception as e:
        component.add_row([operation, "FAILED", str(e)])
    print(component)


main()

