# matrix-bot


## Quick steps

* Installation from PIP:

```
pip install  git+https://github.com/psaavedra/matrix-bot.git
```

* Installation for development:

```
sudo pip install getconf matrix-client==0.0.6 python-dateutil python-ldap python-memcached feedparser pytz requests
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

Notes:

The python-ldap is based on OpenLDAP, so you need to have the development files
(headers) in order to compile the Python module. If you're on Ubuntu, the
package is called libldap2-dev.

Debian/Ubuntu:

$ sudo apt-get install libsasl2-dev python-dev libldap2-dev libssl-dev

RedHat/CentOS:

$ sudo yum install python-devel openldap-devel

TODO: Add a summary and the explanation of this project

TODO: Add examples of usage

TODO: PEP8 and Pyflake revision
