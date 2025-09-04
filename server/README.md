# Server for persistent base impulses storage, polling jobs, sending emails
* serves metric metadata, metric data and handles ingest
* imports metric data from gCal using a polling job

## Some details
* on the server, a hashed encryption token should be stored somewhere
* on app load both the hashed and unhashed token is supplied as an env variable
* user queries (ingest, data points fetch, etc.) - are authenticated via this encryption token
* the oauth2 tokens for gcal integration are encrypted using this encryption token and stored on disk

## To install deps and run
```
cd server
python3 -m venv venv
source ./venv/bin/activate
pip3 install bcrypt
TOKEN='...' HASHED_TOKEN='...' <... other env veriables> python3 run.py
```
## To rotate token on remote machine (need to trigger app restart separately)
### This also needs `bcrypt`, so source the venv
```
REMOTE_HOST=ssh_host ./server/token_update.sh
```
## To deploy (need env variables and ssh access (keys installed))
```
./deploy.sh
```
## To run directly on local machine (need env variables and the python virtual env)
```
python3 -m src.run
```
## Env variables
|variable name|description|is needed for deploy script?|is needed to run directly?|
|-|-|-|-|
|`PORT`|port the application should listen on|\u2714|\u2714|
|`TOKEN`|explained earlier|\u2714|\u2714|
|`GOOGLE_OAUTH2_CREDS`|google oauth2 client credentials|\u2714|\u2714|
|`ORIGIN`|protocol + domain + port(if non default, e.g. non `:443` for https)|\u2714|\u2714|
|`HASHED_TOKEN`|bcrypt-hashed `$TOKEN`|\u2718|\u2714|
|`SSH_PORT`|ssh port of the remote machine|\u2714 |\u2718|
|`SSH_USERNAME`|username on the remote machine|\u2714 |\u2718|
|`REMOTE_HOST`|remote host to ssh to and deploy the app to|\u2714 |\u2718|
