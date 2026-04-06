# This docker-compose.yml is for local development and testing

## Services
* impulse app - doesn't hot-swap, but source code is mounted so changes can be picked up via `docker-compose restart app`
* impulse ui - hot-swap (dev server on `http://localhost:3001/impulses/`)
* sqlite database file stored in the app volume at `server/data-store/impulses.sqlite3`


## What doesn't work on this dev server:
* gCal integration
