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
    config.set("connection", "token", "<insert token from https://www.hipchat.com/account/api>")
    config.add_section("apply_notifications")
    config.set("apply_notifications", "enabled", "yes")
    config.set("apply_notifications", "rooms", "name_or_id_of_room1,name_or_id_of_room2")
    config.add_section("item_notifications")
    config.set("item_notifications", "enabled", "no")
    config.set("item_notifications", "rooms", "name_or_id_of_room1,name_or_id_of_room2")
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


def action_run_end(repo, node, action, duration=None, status=None, **kwargs):
    config = _get_config(repo.path)
    if config is None or \
            not config.has_section("item_notifications") or \
            not config.getboolean("item_notifications", "enabled"):
        return

    if status.skipped:
        status_string = "<b>skipped</b>"
    elif not status.correct:
        status_string = "<b>failed</b>"
    else:
        status_string = "succeeded"

    for room in config.get("item_notifications", "rooms").split(","):
        LOG.debug("posting action apply end notification to HipChat room {room}@{server}".format(
            room=room,
            server=config.get("connection", "server"),
        ))
        _notify(
            config.get("connection", "server"),
            room.strip(),
            config.get("connection", "token"),
            "<b>{node}</b>: {action}: {status_string}".format(
                action=action,
                node=node.name,
                status_string=status_string,
            ),
        )


def apply_start(repo, target, nodes, interactive=False, **kwargs):
    config = _get_config(repo.path)
    if config is None or \
            not config.has_section("apply_notifications") or \
            not config.getboolean("apply_notifications", "enabled"):
        return
    for room in config.get("apply_notifications", "rooms").split(","):
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
    if config is None or \
            not config.has_section("apply_notifications") or \
            not config.getboolean("apply_notifications", "enabled"):
        return
    for room in config.get("apply_notifications", "rooms").split(","):
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


def item_apply_end(
    repo, node, item, duration=None, status_before=None, status_after=None, **kwargs
):
    config = _get_config(repo.path)
    if config is None or \
            not config.has_section("item_notifications") or \
            not config.getboolean("item_notifications", "enabled"):
        return

    if status_before.correct:
        return
    elif status_after is None:
        status_string = "<b>skipped</b>"
    elif status_after.correct:
        status_string = "fixed"
    else:
        status_string = "<b>failed</b>"

    for room in config.get("item_notifications", "rooms").split(","):
        LOG.debug("posting item apply end notification to HipChat room {room}@{server}".format(
            room=room,
            server=config.get("connection", "server"),
        ))
        _notify(
            config.get("connection", "server"),
            room.strip(),
            config.get("connection", "token"),
            "<b>{node}</b>: {item}: {status_string}".format(
                item=item,
                node=node.name,
                status_string=status_string
            ),
        )
