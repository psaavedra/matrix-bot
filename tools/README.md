# Tools

## Echo example

This example demonstrates the Echo plugin.  This plugin simply prints out a
message in a matrix room.  The content of the message as well as the matrix room
can be customized in `echo-test-template.cfg`.

```python
settings['DEFAULT'] = {
    'loglevel': 10,
    'logfile': '/dev/stdout',
    'period': 5
}
settings['matrix'] = {
    'uri': 'https://matrix.example.com',
    'username': 'USER',
    'password': 'PASSWORD',
    'domain': 'example.com',
    'rooms': ['#matrixbot-room'],
    'only_local_domain': False
}

echo_plugin = {
    'module': "matrixbot.plugins.echo",
    'class': "EchoPlugin",
    'settings': {
        'message': 'hello room!',
        'username': 'USER',
        'rooms': ['#matrixbot-room']
    }
}

settings['plugins'] = {}
settings['plugins']['echo'] = echo_plugin
```

When running `echo-test`, the script generates an actual configuration file out
of `echo-test-template.cfg`.  Keywords 'USER' and 'PASSWORD' get replaced by the
actual user and password values passed on calling `echo-test`.  Example:

```bash
$ echo-test --user dpino --password pass
```

In case no user and passord arguments are passed, the values are fetched from
`$HOME/.git-credentials` if the file exists.
