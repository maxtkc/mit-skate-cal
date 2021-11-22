# MIT Skating Calendar

MIT has a pdf skating calendar that they update each month, and updating a
google calendar manually is way too much work, so this should scrape that pdf
and run a caldav server that will provide an updated calendar to users.

# Running the server

```
$ make
$ docker-compose up -d
```
