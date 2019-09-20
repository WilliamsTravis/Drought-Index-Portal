Installation Steps (Anaconda method)

1) Clone repository
2) Get Anaconda
3) Create virtual conda environment from the yaml file

   conda env create -f requirements.yaml

4) Install nginx (Should probably just add this to the requirements file)

   sudo apt-get install nginx

5) Get SSL certificates and configure the webserver

   a) First, go get a domain name and associate it with the public ip address.
      I've been using godaddy.com, but anywill do. You first purchase a domain
      name (www.something.com), then go the DNS management section. Here you'll 
      want to associate the domain with the ip address of whichever connection
      you're going to serve the application from. Here's an example DNS setup
      using mostly defaults with the critical part being the first one:
    
    #> Type 	Name 	         Value                                         TTL 
    #>	a 	@ 	         157.245.191.181                               600 seconds 
    #> cname 	www 	         @                                             1 Hour 
    #> cname 	_domainconnect 	 _domainconnect.gd.domaincontrol.com           1 Hour 
    #> ns 	@ 	         ns53.domaincontrol.com 	               1 Hour 	
    #> ns 	@ 	         ns54.domaincontrol.com                        1 Hour 	
    #> soa 	@ 	         Primary nameserver: ns53.domaincontrol.com.   1 Hour
    
   b) Then install certbot (and by association 'letsencrypt') for nginx:
        1) sudo add-apt-repository ppa:certbot/certbot
	2) sudo apt-get update
	3) sudo apt-get install python-certbot-nginx

   c) Next, generate ssl certificates for the domain from above, take note of where the
      certificates are saved (likely in "/etc/letsencrypt/live/<domain>")
        1)   certbot --nginx -d <domain-name>
	
   d) Okay, so when you run the app it will be directed through a port on the local machine. 
      What we are going to do is tell the webserver (nginx) that it should take what ever
      is running in that port and send it to the domain we set up. To do this we need to
      reconfigure nginx site files.
       1) rm /etc/nginx/sites-available/default
       2) nano (vi, vim, etc...) /etc/nginx/sites-available/flask_settings:
      	  (copy the dictionaries below into the flask_settings file and replace <domain> with
	  the chosen domain name):
	   
	    upstream app_server {
            server 127.0.0.1:8000;
            }

           server {
            listen 443 ssl;
            server_name <domain>;
            ssl_certificate /etc/letsencrypt/live/<domain>/fullchain.pem;
            ssl_certificate_key /etc/letsencrypt/live/<domain>/privkey.pem;

            root /usr/share/nginx/html;
            index index.html index.htm;

            client_max_body_size 4G;
            keepalive_timeout 5;

            location / {
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $http_host; 
            proxy_redirect off;
	    proxy_pass http://app_server;
            }
           }
           server {

            listen 80;
            server_name <domain>;
            return 301 https://$host$request_uri;
           }

       3) Now link the available site configuration file with an enabled file:

	    ln -s /etc/nginc/sites-available/flask_settings /etc/nginx/sites-enabled/flask_settings

       4) Restart or reload nginx

            sudo service nginx reload

       5) if there are problems there may be a typo in the settings file, the wrong ip address, perhaps
          you'll need to delete the default settings in sites-enabled (lot's of causes). Try testing
	  nginx for clues:

	    sudo nginx -t
  
 6) If this works setup the automatic renewal process with crontab. Instructions coming.
 7) Now we need to either download and transform all of the data. There are many sources of data and, at the moment, each has
    its own script.
 7) Now, to run the actual application use a webserver gateway interface like green unicorn. The syntax
    is simple enough:
    gunicorn app:server
	   
#  4) To use more of the computing power add workers and threads:
       # gunicorn -w 3 --threads 3 app:server
   
#  5) To run the application in the back ground so you can leave the computer use a daemon call:
       # gunicorn -w 3 --threads 3 --daemon app:server
   
#  6) Cross fingers.
#  7) Open url in a browser, hopefully it worked!
