## Raspberry PI Jessie configuration
2017/01/17
STATUS: BETA operational local

### Pi 3
Rasberry Pi basisbundel (incl behuizing, 2.5 A adapter, 16 GB micro card) € 65,-
Lunix versie Jessie
Power on with screen: change this if needed via raspi-config

FIRST: make a backup of the micro mem card on your desktop. So you can roll back.

### HEADLESS Pi
No console no screen to the Pi well no problem.
Power on the Pi. Make sure the Pi is connected with a cable to your router.
Try to find the IP address eg via the command "arp -n" something as 192.168.0.34
Connect via ssh: ssh pi@192.168.0.34 use deflt password raspberry
If you are heading for a wireless (wifi) Pi? You have to set up some configuration
on the SD first: see http://dougbtv.com/2016/03/06/raspi-3-headless-wifi/

### FIRST UPGRADE
You need for this to have an internet connection.
You probably do not need the package wolfram-engine (680 MB) so delete the package:
```shell
    sudo apt-get purge wolfram-engine
```
Startup and perform an upgrade:
```shell
    sudo apt-get update     # update package info
    sudo apt-get -y upgrade # upgrade all packages
    sudo apt-get dist-upgrade       # upgrade to latest system packages
    sudo apt-get autoremove # remove packages not longer needed
```

### FIRST CONFIG
initiate/command: `sudo raspi-config` and
expand filesystem if one created new PI OS on mem card.
For now enable start with screen (disable this later) and configure the
localisation options:
```
    set language eg to nl_NL.UTF-8
    set timezone eg Europe/Amsterdam
    set keyboard layout: and check by pushing @-key and see key response.
```
Had to edit /etc/default/keyboard the "gb" setting into "us" as well.

* Change the Pi default password!
```shell
pi% `passwd pi` -> acacadabra 
```
* You need internet connectivity to update the Jessie: `sudo apt-get update upgrade dist-upgrade`. This takes a while ... and finally `sudo apt-get /autoremove`
* Allow to remotely login via ssh (or putty):
```shell
    sudo update-rc.d ssh enable
    sudo service ssh restart
```

Install *git* for the archive downloads from eg github:
```shell
sudo apt-get install git
```

Choose a project name: say BdP
 and Give the pi a nice host name e.g. name: bdp
```shell
sudo hostname bdp
sudo nano /etc/hostname #  and change raspberripi to bdp
```
Is there an internet connectivity? Try: `host 8.8.8.8   # The Google DNS server`

### INSTALL the MySense PROJECT

Download the tar (tgz) fite or clone it from github: 
```shell
sudo git clone https://github.com/teusH/MySense
```
Or use `tar`:
Copy the `MySense.tgz` into the pi user home directory. Unpack the tar file (`tar xzf MySense.tgz`)
Use the `INSTALL.sh` shell file to install all dependent libraries and modules (try: `./INSTALL.sh help`.

### Remote desktop:
Install vnc: `sudo apt-get install tightvncserver`
and start the server: `tightvncserver`. You need to enter some passwords and remember them!
And start a session: `vncserver :0 -geometry 1920x1080 -depth 24`.
You should be able to get a desktop from remote e.g. Apple laptop: start "finder" and
make sure you enabled screen share on your Apple:
Menu item: `Go -> Connect to server ...  vnc://xxx.xxx.xxx.xxx`

### BACKDOOR
You probably want to get in touch with the node for remote management. Make sure you are allowed to walk around on the local network...

The following creates a backdoor :-( to the Pi via internet cloud.
Use `ssh` or if the PI is behind a firewall/router one can use simply *weaved*, or use ssh tunneling or VPN.

#### WEAVED
Install `Weaved`:
Create an account with `weaved.com`: meToo@MyHost.io password a6LpWprG41LD
 and respond with email to verify the account configuration.
Next add your Pi system names names:
```
    name: PI_IoS-BdP_01
    SSH-Pi ssh port 28
    HTTP-Pi HTTP port 8088
```
On your desktop install:
```shell
    sudo apt-get install weavedconnected
    sudo vi /etc/sshd/config add port 28 and service sshd reload
    sudo weavedinstaller
```
    check: webbrowser login  with weaved.com login desk and push SSH-Pi: proxy/portnr
```
    ssh -l pi proxy??.weabevd.com -p "35757"
    # on your Pi
    sudo crontab -e and add line:
        @reboot /usr/bin/weavedstart.sh
```
*notice*: everyone with weaved password or proxy/port (and so weaved.com)
*notice*: and  knowing PI login/passwd can log into your PI via ssh!

Maybe you should better use *ssh tunneling* (please complete this one)

### USERS:
Install Internet of Sense user say *ios* (full name Internet of Sense):
```shell
    sudo adduser ios
    sudo passwd ios
```
and add the user *ios* to `/etc/sudoers` list:
```shell
    sudo su
    echo "ios ALL=(ALL) PASSWD: ALL" >>/etc/sudoers.d/020_ios-passwd
```
and test in another window if login/sudo works for ios user before proceeding.
In this home dir please install all MySense sources, eg in the directory MySense.

### Install modules using github:
Install eg in IoS home dir: `git clone https://github.com/<module name>`.
change dir into github project name and use `python setup.py install` (see REAME.md)
For python 3 use the command python3.

### PYTHON:
Update first your Pi: `sudo apt-get update``
Install the *python installer*: `apt-get install python-pip`
Make sure you have the latest openssl: `sudo apt-get install python-openssl`

For other modules/libraries needed by the MySense.py script see README.mysense
The collection of apt-get install, pip install and github setup.py install
will install the needed modules.
    
### Pi may have USB serial failures :-(
The Pi with several USB connection may run out of energy. If so you will see intermittant USB serial failures. One way to solve this is to use a quality USBhub with own power adapter of say 2.5A.