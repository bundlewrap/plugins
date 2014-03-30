#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import unicode_literals

from json import loads
from os import listdir
from os.path import isdir, isfile, join

from update_index import BASE_PATH, hash_directory


def fail(msg):
    print(msg)
    exit(1)


with open(join(BASE_PATH, "index.json")) as f:
    index = loads(f.read())

for plugin in listdir(BASE_PATH):
    if not isdir(join(BASE_PATH, plugin)) or plugin == ".git":
        continue
    print("{plugin}: checking...".format(plugin=plugin))

    # read plugin manifest
    with open(join(BASE_PATH, plugin, "manifest.json")) as f:
        manifest = loads(f.read())

    # hash plugin directory
    dir_hash = hash_directory(join(BASE_PATH, plugin))

    if dir_hash != index[plugin]['checksum']:
        fail(
            "{plugin}: Checksum doesn't match. "
            "Did you run update_index.py?".format(plugin=plugin)
        )

    if manifest['version'] != index[plugin]['version']:
        fail(
            "{plugin}: Version doesn't match. "
            "Did you run update_index.py?".format(plugin=plugin)
        )

    for file_path in manifest['provides']:
        if not isfile(join(BASE_PATH, plugin, file_path)):
            fail(
                "{plugin}: '{file}' listed in manifest, but doesn't exist".format(
                    plugin=plugin,
                    file=file_path,
                )
            )

    if not isfile(join(BASE_PATH, plugin, "AUTHORS")):
        fail("{plugin}: missing AUTHORS".format(plugin=plugin))

    if not isfile(join(BASE_PATH, plugin, "LICENSE")):
        fail("{plugin}: missing LICENSE".format(plugin=plugin))

    print("{plugin}: OK".format(plugin=plugin))

print("Everything seems to be in order.")
