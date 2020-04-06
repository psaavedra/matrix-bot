# matrix-bot


## Quick steps

* Installation from PIP:

```
pip install  git+https://github.com/psaavedra/matrix-bot.git
```

* Installation for development:

```
sudo pip install getconf matrix-client==0.0.6 python-ldap python-memcached feedparser pytz requests
git clone http://github.com/psaavedra/matrix-bot.git
cd matrix-bot/
cd tools/
ln -s ../matrixbot matrixbot
./matrix-bot --help
cat <<EOF > test.cfg
settings["DEFAULT"] = {
    "loglevel": 10,
    "logfile": "/dev/stdout",
    "period": 5,
}
settings["matrix"] = {
    "uri": "https://matrix.org",
    "username": "user",
    "password": "password",
    "domain": "matrix.org",
    "rooms": [ ],
}
EOF
./matrix-bot -c test.cfg
```



TODO: Add a summary and the explanation of this project

TODO: Add examples of usage

TODO: PEP8 and Pyflake revision
