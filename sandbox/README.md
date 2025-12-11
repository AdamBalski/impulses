# This docker-compose.yml is for local development and testing

## Services
* postgresql
* impulse app - doesn't hot-swap, but source code is mounted so changes can be picked up via `docker-compose restart app`
* impulse ui - hot-swap (dev server)


## What doesn't work on this dev server:
* gCal integration