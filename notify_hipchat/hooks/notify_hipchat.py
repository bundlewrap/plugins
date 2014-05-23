from ConfigParser import SafeConfigParser
from json import dumps
from os.path import exists, join

try:
    from requests import post
    from requests.exceptions import ConnectionError
    REQUESTS = True
except ImportError:
    REQUESTS = False

from blockwart.utils import LOG


def _create_config(path):
    LOG.debug("writing initial config for HipChat notifications to .hipchat_secrets.cfg")
    config = SafeConfigParser()
    config.add_section("configuration")
    config.set("configuration", "enabled", "unconfigured")
    config.add_section("connection")
    config.set("connection", "server", "api.hipchat.com")
    config.set("connection", "rooms", "name_or_id_of_room1,name_or_id_of_room2")
    config.set("connection", "token", "<insert token from https://www.hipchat.com/account/api>")
    with open(path, 'wb') as f:
        config.write(f)


def _get_config(repo_path):
    config_path = join(repo_path, ".hipchat_secrets.cfg")
    if not exists(config_path):
        _create_config(config_path)
    config = SafeConfigParser()
    config.read(config_path)
    if config.get("configuration", "enabled") == "unconfigured":
        LOG.error("HipChat notifications not configured. Please edit .hipchat_secrets.cfg "
                  "(it has already been created) and set enabled to 'yes' "
                  "(or 'no' to silence this message and disable HipChat notifications).")
        return None
    elif config.get("configuration", "enabled").lower() not in ("yes", "true", "1"):
        LOG.debug("HipChat notifications not enabled in .hipchat_secrets.cfg, skipping...")
        return None
    elif not REQUESTS:
        LOG.error("HipChat notifications need the requests library. "
                  "You can usually install it with `pip install requests`.")
        return None
    return config


def _notify(server, room, token, message):
    try:
        post(
            "https://{server}/v2/room/{room}/notification?auth_token={token}".format(
                token=token,
                room=room,
                server=server,
            ),
            headers={
                'content-type': 'application/json',
            },
            data=dumps({
                'color': 'purple',
                'message': message,
                'notify': True,
            }),
        )
    except ConnectionError as e:
        LOG.error("Failed to submit HipChat notification: {}".format(e))


def apply_start(repo, target, nodes, interactive=False, **kwargs):
    config = _get_config(repo.path)
    if config is None:
        return
    for room in config.get("connection", "rooms").split(","):
        LOG.debug("posting apply start notification to HipChat room {room}@{server}".format(
            room=room,
            server=config.get("connection", "server"),
        ))
        _notify(
            config.get("connection", "server"),
            room.strip(),
            config.get("connection", "token"),
            (
                "Starting {interactive}interactive "
                "bw apply on <b>{target}</b>..."
            ).format(
                interactive="non-" if not interactive else "",
                target=target,
            ),
        )


def apply_end(repo, target, nodes, duration=None, **kwargs):
    config = _get_config(repo.path)
    if config is None:
        return
    for room in config.get("connection", "rooms").split(","):
        LOG.debug("posting apply end notification to HipChat room {room}@{server}".format(
            room=room,
            server=config.get("connection", "server"),
        ))
        _notify(
            config.get("connection", "server"),
            room.strip(),
            config.get("connection", "token"),
            "Finished bw apply on <b>{target}</b>.".format(target=target),
        )
