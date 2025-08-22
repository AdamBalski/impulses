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
TOKEN='...' HASHED_TOKEN='...' python3 run.py
```
## To rotate token on remote machine (need to trigger app restart separately)
```
REMOTE_HOST=ssh_host ./server/token_update.sh
```
