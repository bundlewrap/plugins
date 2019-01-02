#!/usr/bin/env python


import hashlib
from json import loads, dumps
from os import listdir, walk
from os.path import dirname, isdir, join, realpath

BASE_PATH = dirname(realpath(__file__))


def hash_directory(path):
    hasher = hashlib.sha1()
    filelist = []
    for root, dirs, files in walk(path):
        for file in files:
            filelist.append(join(root, file))
    filelist.sort()
    for file in filelist:
            with open(join(root, file)) as f:
                hasher.update(f.read().encode("utf-8"))
    return hasher.hexdigest()


if __name__ == '__main__':
    new_index = {}
    with open(join(BASE_PATH, "index.json")) as f:
        old_index = loads(f.read().encode("utf-8"))

    for plugin in listdir(BASE_PATH):
        if not isdir(join(BASE_PATH, plugin)) or plugin == ".git":
            continue

        # read plugin manifest
        with open(join(BASE_PATH, plugin, "manifest.json")) as f:
            manifest = loads(f.read().encode("utf-8"))

        # hash contents of plugin directory
        dir_hash = hash_directory(join(BASE_PATH, plugin))

        new_index[plugin] = {
            'checksum': dir_hash,
            'desc': manifest['desc'],
            'version': manifest['version'],
        }

        if plugin in old_index:
            if new_index[plugin]['checksum'] != old_index[plugin]['checksum'] and \
                    not new_index[plugin]['version'] > old_index[plugin]['version']:
                raise ValueError("contents for {} changed, but version wasn't incremented".format(plugin))

            if new_index[plugin]['version'] > old_index[plugin]['version']:
                print(("{plugin}: version {oldversion} -> {newversion}".format(
                    newversion=new_index[plugin]['version'],
                    plugin=plugin,
                    oldversion=old_index[plugin]['version'],
                )))
        else:
            print(("{plugin}: added".format(plugin=plugin)))

    with open(join(BASE_PATH, "index.json"), "w") as f:
        f.write(dumps(new_index, indent=4, sort_keys=True) + "\n")
