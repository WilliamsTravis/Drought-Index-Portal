#!/bin/bash

# This is an attempt to automate the process of setting up a computer to run a DASH app.
# To make this file work do this:

# 1) Add <export PATH=$PATH:/bin> to .profile or .bash_profile
# 2) Make this file executable using <chmod u+x setup.sh>
# 3) Ideally, run the line <./setup.sh> and wait!

# Things to do:

# 1) Turn paths into variables. Use this site:
	# <https://www.taniarascia.com/how-to-create-and-use-bash-scripts/>
# 2) Plenty more I'm sure...

echo -- Is this where want to install everything, y/n?

read response

if [ $response = y ] || [ $response = Y ] || [ $response = yes ] || [ $response = Yes ]
then
    echo -- Okay, installing virtual enviornment, a web server, and a web server gateway interface

    apt-get update && apt-get upgrade
    apt-get install nginx
    pip3.6 install gunicorn
    pip3.6 install virtualenv
    sudo add-apt-repository -y ppa:ubuntugis/ppa
    sudo apt install gdal-bin python-gdal python3-gdal
    sudo virtualenv env
    source env/bin/activate
    pip install -r requirements
fi


# I Couldn't get it to work in the virtual environment, as you can see. Will work on that.
# After the installation above there are just a few steps needed to configure nginx to run the
# app:
# 1) rm /etc/nginx/sites-available/default

# 2) nano /etc/nginc/site-available/flask_settings
#     This step would take a lot to automate, but with the ip address and the project folder
#     it should be doable. For now, use this site, it has the simplest template I could find:
#            "https://edward.io/blog/flask-gunicorn-nginx.html"

# 3) sudo nginx -t
#       This is just a test. If it fails there's probably a typo in the flask_setting doc

# 4) ln -s /etc/nginc/sites-available/flask_settings /etc/nginx/sites-enabled/flask_settings
#        I had to fiddle with this...I've seen it explained that you do and dont
#          need to specify the doc name in sites-enabled

# 5) sudo service nginx reload
#       Is it always reload? Could've sworn I saw restart in another tutorial


# Establishing SSL certificates:

# 6) Okay, now we should be able to visit the site using the public ip address, but what if
#       we want a ssl certificates or to embed the app in an iframe? Each of these require a
#       a domain and nginx configuration changes. First, go get a domain name and associate it
#       with the public ip address.
#  7) Then install lets encrypt and the certboth for nginx:
#       1) sudo add-apt-repository ppa:certbot/certbot
#       2) sudo apt-get update
#       3) sudo apt-get install python-certbot-nginx
#  8) Then change the server name in flask_settings to the domain name or names
#  9) Check for errors
#	1) sudo nginx -t
#	2) sudo service nginx reload
#  10) Allow https through firewall
# 	1) check the firewall status: sudo ufw status
#       2) Is https allowed? If Nginx HTTP is instead do this:
#		sudo ufw all 'Nginx Full'
#		sudo ufw delete allow 'Nginx HTTP'
#  11) Get certificate
#	1) sudo certbot --nginx -d <domain_name>
#  12) If this works setup the automatic renewal process with crontab
