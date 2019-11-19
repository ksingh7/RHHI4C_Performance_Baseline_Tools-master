
# Setup guide for DS2 / DS3
Credits to my colleague [Marko Karg](https://github.com/mkarg75)

## DS3 Dataset Generation Process - "The Hard Way"

- In the next section you can learn about a simple way for Dataset generation

### Requirements: 

- A (virtual) machine with git, mariadb-server and mariadb installed. Follow readme.md file and use ansible role to insstall database.
- Cinder RBD (coming from Ceph) to be mounted on /var/lib/mysql

### Dataset generation for DS3 

- Clone the DVD Store 3 repository
```
git clone https://github.com/dvdstore/ds3.git
```

- Change directory to the ds3/ds3 dir and run the Install_dVDStore.pl script:
```
cd ds3/ds3 ; perl Install_DVDStore.pl
```

- To generate a 10GB MySQL dataset on a linux machine answer the questions as follows
```
[root@rhhi-perf2 ds3]# perl Install_DVDStore.pl 
Please enter following parameters: 
***********************************
Please enter database size (integer expected) : 10
Please enter whether above database size is in (MB / GB) : GB
Please enter database type (MSSQL / MYSQL / PGSQL / ORACLE) : MYSQL
Please enter system type on which DB Server is installed (WIN / LINUX) : LINUX
```

- The script will now create a couple of CSV files which will be used for the content creation in the DB.
- Make sure mysql / mariadb is up and running:
```
[root@rhhi-perf2 ~]# systemctl status mariadb
● mariadb.service - MariaDB database server
   Loaded: loaded (/usr/lib/systemd/system/mariadb.service; enabled; vendor preset: disabled)
   Active: active (running) since Di 2018-10-02 10:35:12 UTC; 8s ago
 ```

- Create the db user ``web`` and set its password to ``web``:
```
mysql -u root
CREATE USER 'web'@'localhost' IDENTIFIED BY 'web';
GRANT ALL PRIVILEGES ON *.* to 'web'@'localhost' IDENTIFIED BY 'web';
flush privileges;
exit
```
- Change into the ``mysqlds3`` directory in the ds3 parent and run the ``mysqlds3_create_all.sh`` script
``Warning messgaes about using password via command line are normal......``
```
Creating database
Creating Indexes
Creating Stored Procedures
Loading Customer Data
Loading Orders Data
Loading Orderlines Data
Loading Customer History Data
Loading Products Data
Loading Inventory Data
Loading Membership data
Loading Reviews data
Loading Reviews Helpfulness Ratings Data
....
....
```
- This script will generate the database contents, depending on the size you chose this might take couple of hours at least.
- Once the dataset generation is completed, start MySQL to verify the contents

```
systemctl start mariadb
mysql -u web -p
web
use DS3;
show tables;
select count(*) from CUSTOMERS;
select * from CUSTOMERS limit 1;
```
- Copy this generated dataset to all other VMs in your environment. Before that Ceph RBD is properly mounted on all VMs and MySQL is
configured to use Ceph RBD
- Stop database on all nodes and ``rsync`` the contents of ``/var/lib/mysql`` to the other VMs in our environment

```
systemctl stop mariadb ; systemctl status mariadb

for i in {2..10} ; do ssh server-$i systemctl stop mariadb ; done
for i in {2..10} ; do ssh server-$i systemctl status mariadb ; done

cd /var/lib/mysql ;
for i in {2..10} ; do ( rsync -avz --checksum * server-$i:/var/lib/mysql &) ; done
```
- Its time to start MySQL database containing the dataset for DS3 that we have generated
```
for i in {1..10} ; do ssh server-$i systemctl start mariadb ; done
for i in {1..10} ; do ssh server-$i systemctl status mariadb ; done
for i in {1..10} ; do echo ------ server-$i ----- ; ssh server-$i "mysql -u web -pweb  DS3 -e 'show tables'" ; done
```

## DS3 Dataset Generation Process - "The Simple Way"

### Requirements: 

- A (virtual) machine with git, mariadb-server and mariadb installed. Follow readme.md file and use ansible role to install database.
- It is assumed that you are follow this in an OpenStack environment

### Step-1 :: Download and configure DS3 Dataset on Admin Node 

1. Perform the following steps on the VM. From here on we will call this VM as ``admin node``

  - Create a Cinder volume (200G in size) and attach it to admin node

2. Login to the admin vm and perform the following actions
  
  ```
  systemctl stop mariadb
  umount /var/lib/mysql
  mkfs.xfs /dev/vdc
  mount /dev/vdc /var/lib/mysql
  cd /var/lib/mysql
  wget https://s3-eu-west-1.amazonaws.com/ds3-mysql-50gb/var-lib-mysql-ds3-50gb.tar
  tar -xvf var-lib-mysql-ds3-50gb.tar
  cd var/lib/mysql
  mv * ../../..
  ```
  
3. Comment ``innodb_log_file_size`` in ``/etc/my.cnf``
 
 ```
 sed -e '/innodb_log_file_size/ s/^#*/#/' -i /etc/my.cnf
 ```
 
4. Start MySQL
 
 ``` 
 chown -R mysql:root /var/lib/mysql
 restorecon -R /var/lib/mysql/
 systemctl restart mariadb
 ```

5. Create a user in MySQL

  ```
  mysql -u root
  CREATE USER 'web'@'localhost' IDENTIFIED BY 'web';
  GRANT ALL PRIVILEGES ON *.* to 'web'@'localhost' IDENTIFIED BY 'web';
  flush privileges;
  exit
  ```
6. Verify you are able to query the dataset tables

  ```
  mysql -u web -pweb DS3 -e "select username,password from CUSTOMERS LIMIT 5"
  ```

You should able to see the ``CUSTOMERS`` table records.


### Step-2 :: Add the Dataset to all the VMs

1. Stop MySQL database on the admin node. 
  
  ```
  systemctl stop mariadb
  umount /var/lib/mysql

  ```
 
2. Create cinder snapshot from undercloud node
  
  ```
  source overcloudrc
  openstack volume snapshot list
  openstack volume snapshot create --volume 0db9629d-47ea-4d9a-90c6-c6fd709a05a5 --description "DS3 50G Dataset snapshot" --force DS3_50G_Dataset 
  openstack volume snapshot list  
  ```

3. Increase volume creation quota
    
  ``` 
  openstack quota set admin --volumes 40 --gigabytes 8000
  ```

4. Create volumes for each VM from Snapshot
  
  ```
  for i in {1..10} ; do openstack volume create --snapshot 098bdbb0-7620-418a-929d-73ee604e30c9 --description "DS3 Volume server-$i" DS3-volume-server-$i ; done
  ```

5. Attach the dataset volume to each VM

  ```
  for i in {1..10} ; do openstack server add volume server-$i DS3-volume-server-$i ; done
  ```

6. Using ansible configure each of these VMs

  ```
  ansible all --key=~/stack.pem -m shell -a "hostname"
  ansible all --key=~/stack.pem -b -m shell -a "systemctl stop mariadb"
  ansible all --key=~/stack.pem -b -m shell -a "umount /var/lib/mysql"
  ansible all --key=~/stack.pem -b -m shell -a "lsblk"
  ansible all --key=~/stack.pem -b -m shell -a "mount /dev/vdc /var/lib/mysql"
  ansible all --key=~/stack.pem -b -m shell -a "chown -R mysql:root /var/lib/mysql"
  ansible all --key=~/stack.pem -b -m shell -a "restorecon -R /var/lib/mysql/"
  ansible all --key=~/stack.pem -b -m shell -a "rm -rf /var/lib/mysql/var-lib-mysql-ds3-50gb.tar"
  ansible all --key=~/stack.pem -b -m shell -a "sed -e '/innodb_log_file_size/ s/^#*/#/' -i /etc/my.cnf"
  ansible all --key=~/stack.pem -b -m shell -a "systemctl restart mariadb"
  ansible all --key=~/stack.pem -b -m shell -a "systemctl status mariadb"
  ansible all --key=~/stack.pem -b -m shell -a "mysql -u web -pweb DS3 -e 'select username,password from CUSTOMERS LIMIT 1' "
 ```
 
At this point you should have 10 VMs with their own 50G DS3 dataset.

## DS3 Webserver Setup Instructions

- DS3 webserver uses apache, to setup use ansible playbook 

```
ansible-playbook site.yaml --key=~/stack.pem -t ds3
```
- Test the DS3 webserver

```
http://172.21.1.161/ds3/dslogin.php?username=user1&password=password
```

## DS3 Performance Test



