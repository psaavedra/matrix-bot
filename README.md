# matrix-bot

## Dependencies

Run script `install-package-dependencies.sh` to install all the required dependencies.

Systems supported: Debian, Ubuntu & RedHat.

## Install

### Installation from PIP

```
$ pip install git+https://github.com/psaavedra/matrix-bot.git
```

### Installation for development

```
$ git clone http://github.com/psaavedra/matrix-bot.git
$ cd matrix-bot/
$ ./install-dependencies.sh
$ ln -s $PWD/matrixbot $PWD/tools/matrixbot
$ ln -s tools/matrix-bot
$ cat > test.cfg <<EOF
$ settings["DEFAULT"] = {
$     "loglevel": 10,
$     "logfile": "/dev/stdout",
$     "period": 5,
$ }
$ settings["matrix"] = {
$     "uri": "https://matrix.org",
$     "username": "user",
$     "password": "password",
$     "domain": "matrix.org",
$     "rooms": [ ],
$ }
$ EOF
$ ./matrix-bot -c test.cfg
```

TODO: Add a summary and the explanation of this project

TODO: Add examples of usage

TODO: PEP8 and Pyflake revision
