#!/bin/bash

# This is an attempt to automate the process of setting up a computer to run a DASH app.
# To make this file work do this:

# 1) Add <export PATH=$PATH:/bin> to .profile or .bash_profile
# 2) Make this file executable using <chmod u+x setup.sh>
# 3) Ideally, run the line <./setup.sh> and wait!

# Things to do:

# 1) Turn paths into variables. Use this site:
	# <https://www.taniarascia.com/how-to-create-and-use-bash-scripts/>
# 2) Automate the nginx configuration step
# 3) I'm not sure I could automate the LetsEncrpyt step, too many prompts
# 4) Actually, the letsencrypt step needs to happen first since the results from that are used in the nginx step
# 5) Which means, well, is it worth it to automate anything else? I guess if I could automate Letsencrypt responses.

echo -- Okay, installing the Python parts into a virtual environment...you will still need to configure webserver and establish ssl certificates. Also, don't forget to download the data.
sudo apt-get update && apt-get upgrade
sudo apt-get install nginx
pip install virtualenv
sudo add-apt-repository -y ppa:ubuntugis/ppa
sudo apt install gdal-bin python-gdal python3-gdal
sudo virtualenv env
source env/bin/activate
pip install -r requirements



# MANUAL INSTRUCTIONS
# You may also wish to use conda



# Web server steps
# 1) Set up ssl certificates so we can use a secure https connection
   # a) First, go get a domain name and associate it with the public ip address.
     # I've been using godaddy.com, but anywill do. You first purchase a domain
     # name (www.something.com), then go the DNS management section. Here you'll 
     # want to associate the domain with the ip address of whichever connection
     # you're going to serve the application from. Here's an example DNS setup
     # using mostly defaults with the critical part being the first one:
    
    #Type 	Name 	         Value                                         TTL 
    #	a 	@ 	         157.245.191.181                               600 seconds 
    # cname 	www 	         @                                             1 Hour 
    # cname 	_domainconnect 	 _domainconnect.gd.domaincontrol.com           1 Hour 
    # ns 	@ 	         ns53.domaincontrol.com 	               1 Hour 	
    # ns 	@ 	         ns54.domaincontrol.com                        1 Hour 	
    # soa 	@ 	         Primary nameserver: ns53.domaincontrol.com.   1 Hour
    
   # b) Then install certbot (and by association 'letsencrypt') for nginx:
	# 1) sudo add-apt-repository ppa:certbot/certbot
	# 2) sudo apt-get update
	# 3) sudo apt-get install python-certbot-nginx

   # c) Next, generate ssl certificates for the domain from above, take note of where the
        # certificates are saved (likely in "/etc/letsencrypt/live/<domain>")
        # 1)   certbot --nginx -d <domain-name>
	
   # d) Okay, so when you run the app it will be directed through a port on the local machine. 
      # What we are going to do is tell the webserver (nginx) that it should take what ever
      # is running in that port and send it to the domain we set up. To do this we need to
      # reconfigure nginx site files.
       # 1) rm /etc/nginx/sites-available/default
       # 2) nano (vi, vim, etc...) /etc/nginx/sites-available/flask_settings:
       	   # (copy the dictionaries below into the flask_settings file and replace <domain names> with
	   # the one above, and uncomment everything):
	   
	   # upstream app_server {
           # server 127.0.0.1:8000;
           # }

          # server {
          #  listen 443 ssl;
          #  server_name  www.reservoir-management-game.co;
          #  ssl_certificate /etc/letsencrypt/live/www.reservoir-management-game.co/fullchain.pem;
          #  ssl_certificate_key /etc/letsencrypt/live/www.reservoir-management-game.co/privkey.pem;

          #  root /usr/share/nginx/html;
          #  index index.html index.htm;

          #  client_max_body_size 4G;
          #  keepalive_timeout 5;

          #  location / {
          #  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          #  proxy_set_header Host $http_host; 
          #  proxy_redirect off;
	  #  proxy_pass http://app_server;
          #  }
          # }
          # server {

          #  listen 80;
          #  server_name www.reservoir-management-game.co;
          #  return 301 https://$host$request_uri;
          # }

       # 3) Now link the available site configuration file with an enabled file:
	   # ln -s /etc/nginc/sites-available/flask_settings /etc/nginx/sites-enabled/flask_settings
       # 4) Restart or reload nginx
           # sudo service nginx reload
       # 5) if there are problems there may be a typo in the settings file, the wrong ip address, perhaps
           # you'll need to delete the default settings in sites-enabled (lot's of causes). Try testing
	   # sudo nginx for clues:
	   # sudo nginx -t
  
#  2) If this works setup the automatic renewal process with crontab. Instructions coming.
#  3) Now, to run the actual application use a webserver gateway interface like green unicorn. The syntax
      # is simple enough:
      # gunicorn app:server
	   
#  4) To use more of the computing power add workers and threads:
       # gunicorn -w 3 --threads 3 app:server
   
#  5) To run the application in the back ground so you can leave the computer use a daemon call:
       # gunicorn -w 3 --threads 3 --daemon app:server
   
#  6) Cross fingers.
#  7) Open url in a browser, hopefully it worked!
     
