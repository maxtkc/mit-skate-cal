# MIT Skating Calendar

MIT has a pdf skating calendar that they update each month, and updating a
google calendar manually is way too much work, so this should scrape that pdf
and run a caldav server that will provide an updated calendar to users.

# Running the server

```
$ touch config.env
$ mkdir radicale_data
$ docker-up -d radicale
```

This will get the `radicale` server running so you can create a user.

```
# Create a new htpasswd file with the user "root"
$ docker exec -ti radicale htpasswd -B -c /var/radicale_data/users root
New password:
Re-type new password:
```

Open the web console `http://localhost:8000` and create a new calendar with the
web interface.

Modify the file `config.env` at the root of the repo with the following information:

```
CALENDAR_ID=519e83f2-512d-a940-1785-7fc38636e64
CALDAV_PASSWORD=your-password
```

Then run again with this set and the calendar should update.

```
$ make
$ docker-compose up -d
```
