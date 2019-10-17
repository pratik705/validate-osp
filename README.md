# validate-osp
Validate Open Stack components(Overcloud) by creating a test resources. 

There is "overcloud_conf.ini" file where you need to specify which OSP component
you want to validate. Based on the selected component, resources will be created
on the existing OSP/overcloud

## Installation:
  ```
    - Clone the git repository on the undercloud node
      $ git clone https://github.com/pratik705/validate-osp.git
  ```
 
## Usage:
  ```
  $ cd validate-osp

  $ python osp-testing.py  -h
  usage: osp-testing.py [-h] ticket_id

  Test RHOS components functionality

  positional arguments:
    ticket_id   Maintenance ticket ID / Random string

  optional arguments:
    -h, --help  show this help message and exit


  $ source ~/<overcloudrc>
  $ python osp-testing.py 191017-01170
  Neutron is true
  +---------------------------+---------+--------------------------------------+
  |         Operation         |  Status |              Result/ID               |
  +---------------------------+---------+--------------------------------------+
  |       Create Network      | SUCCESS | fc2baad1-1011-4051-8434-7a7769109744 |
  |       Create Subnet       | SUCCESS | 2c7215e4-a2e3-43e7-8998-d213de696849 |
  |       Create Router       | SUCCESS | cb0bcdaa-d506-4921-b0f4-f5374f7f7297 |
  |  Attach subnet to router  | SUCCESS |                  -                   |
  | Set external GW to router | SUCCESS |                  -                   |
  |     Create Floating IP    | SUCCESS |            172.23.232.159            |
  | Detach Subnet from Router | SUCCESS |                  -                   |
  |       Delete Router       | SUCCESS | cb0bcdaa-d506-4921-b0f4-f5374f7f7297 |
  |       Delete Network      | SUCCESS | fc2baad1-1011-4051-8434-7a7769109744 |
  |     Delete Floating IP    | SUCCESS |            172.23.232.159            |
  +---------------------------+---------+--------------------------------------+

  $ python osp-testing.py 191017-01170
  Neutron is true
  Glance is true
  Nova is true
  +---------------------------+---------+--------------------------------------+
  |         Operation         |  Status |              Result/ID               |
  +---------------------------+---------+--------------------------------------+
  |       Create Network      | SUCCESS | ae2d2890-c092-404d-b3cb-f1fabb162a8d |
  |       Create Subnet       | SUCCESS | 63694087-4287-4e3b-b523-a7eaad793a08 |
  |       Create Router       | SUCCESS | ce6123ea-4178-4f0e-bfd4-cd5be76859b7 |
  |  Attach subnet to router  | SUCCESS |                  -                   |
  | Set external GW to router | SUCCESS |                  -                   |
  |     Create Floating IP    | SUCCESS |            172.23.232.107            |
  |        Create Image       | SUCCESS | e4865da4-2f1b-4373-a8b3-70874b6e20e8 |
  |       Create Flavor       | SUCCESS | 09781122-877a-45ae-aaf8-eb4031bd39c1 |
  |       Create Keypair      | SUCCESS |    rax-test-keypair-191017-01170     |
  |      Create Instance      | SUCCESS | 25b437d7-4834-4599-9fc3-a0a8cc7851ce |
  |     Assign Floating IP    | SUCCESS |                  -                   |
  |      Delete instance      | SUCCESS | 25b437d7-4834-4599-9fc3-a0a8cc7851ce |
  | Detach Subnet from Router | SUCCESS |                  -                   |
  |       Delete Router       | SUCCESS | ce6123ea-4178-4f0e-bfd4-cd5be76859b7 |
  |       Delete Network      | SUCCESS | ae2d2890-c092-404d-b3cb-f1fabb162a8d |
  |     Delete Floating IP    | SUCCESS |            172.23.232.107            |
  |        Delete Image       | SUCCESS | e4865da4-2f1b-4373-a8b3-70874b6e20e8 |
  |       Delete Keypair      | SUCCESS |    rax-test-keypair-191017-01170     |
  |       Delete Flavor       | SUCCESS | 09781122-877a-45ae-aaf8-eb4031bd39c1 |
  +---------------------------+---------+--------------------------------------+
  ```
  
## overcloud_conf.ini
  ```
  [neutron]
  ## Enabling "[neutron]" will perform following operations:
  ## - Create network 
  ## - Create subnet
  ## - Create router
  ## - Attach subnet to router 
  ## Once all above operations are successful, resources will be deleted

  ## external-network-id [OPTIONAL]: If "external-network-id" is set then, test router will be created with
  ## external gateway and floating IP will be created
  external-network-id=f4d6e1be-45fa-4a1b-9040-a812726e2a85



  #[glance]
  ## Enabling "[glance]" will perform following operations:
  ## - Create image
  ## Once image is successfully created, it will be removed.

  ## image_absolute_path [REQUIRED]: Absolute path of the glance image to upload
  #image_absolute_path=~/cirros-0.4.0-x86_64-disk.img



  #[nova]
  ## If you want to test "nova" then, enable "[glance]" section and speciy glance image in
  ## "image_absolute_path" variable.

  ## Enabling "[nova]" will perform following operations:
  ## - Create Image
  ## - Create Network
  ## - Create Subnet
  ## - Create Router
  ## - Attach subnet to router
  ## - Create Flavor
  ## - Create Keypair
  ## - Create Instance
  ## Once instance is successfully created, resources will remain unless "delete" is set to true.

  ## If instance is required to have floating IP then, enable "[neutron]" section and specify external 
  ## network id in "external-network-id" variable.

  ## timeout [OPTIONAL]: timeout value[seconds] to create a instance. If the environment is slow, then increase it accordingly. 
  ## Default value is 60 
  #timeout = 120

  ## delete [OPTIONAL]: If the resources are required to be removed then, set it to "true".
  ## Default value is false
  #delete = true



  #[cinder]
  ## check_service_status [OPTIONAL]: Check cinder* service status. If its set to true, if any of the service is down, validation will stop
  ## If the flag is disabled then, it will ignore the status of the cinder* service and try to validate cinder
  ## Default value is false
  #check_service_status = true

  ## volume_type [OPTIONAL]: Cinder volume type where you want to create a volume. 
  ## Default value is None
  #volume_type = "abc"

  #timeout = 10
  ```
