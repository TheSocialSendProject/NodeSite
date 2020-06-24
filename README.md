# NodeSite
Node Status Page Daemon.

Displays node info on simple static webpage with basic API to coin daemon.

## Depends
 - `nginx`
 - `python 3.x`
 - `python cherrypy`
 - `coin daemon rpc`
 
## Install
 - git clone repo to `/var/www/nodesite`
   - `cd /var/www`
   - `git clone https://github.com/squidicuzz/SendyNode.git nodesite`
 - install deps
   - `apt-get install python3-pip`
   - `pip3 install cherrpy`
 - make launch script excecutable
   - `chmod 755 /var/www/nodesite/scripts/launch`
 - setup config..
   - `cd /var/www/nodesite`
   - `mkdir .env && cp default.conf.json .env/conf.json`
   - edit config: set rpc user and password.
 - setup nginx config for site
   - proxy pass `/api/` to `127.0.0.1:8771` with nginx
 ```
        root /var/www/nodesite/public/;
        index index.html;

        location /api/ {
                proxy_set_header  Host $host;
                proxy_set_header  X-Real-IP $remote_addr;
                proxy_set_header  X-Forwarded-Proto https;
                proxy_set_header  X-Forwarded-For $remote_addr;
                proxy_set_header  X-Forwarded-Host $remote_addr;
                proxy_pass    http://127.0.0.1:8771/;
        }
```
 
 ## Running
  - Assure nginx is setup and restarted..
  - Assure coin daemon is active and `/var/www/nodesite/.env/conf.json` is setup correclty.
  - launch daemon with `./launch start` from `/var/www/nodesite/scripts`
