try:
    from configparser import SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser
from json import dumps
from os.path import exists, join

try:
    from requests import post
    from requests.exceptions import ConnectionError
    REQUESTS = True
except ImportError:
    REQUESTS = False

from bundlewrap.utils.ui import io


def _check_allowed_groups(config, nodes):
    allowed_nodes = set([])

    for node in nodes:
        for allowed_group in config.get("apply_notifications", "allow_groups").split(","):
            if not allowed_group.strip() or node.in_group(allowed_group.strip()):
                allowed_nodes.add(node)

    for node in nodes:
        for denied_group in config.get("apply_notifications", "deny_groups").split(","):
            if node.in_group(denied_group) and node in allowed_nodes:
                allowed_nodes.remove(node)

    return bool(allowed_nodes)


def _create_config(path):
    io.debug("writing initial config for Slack notifications to .slack.cfg")
    config = SafeConfigParser()
    config.add_section("configuration")
    config.set("configuration", "enabled", "unconfigured")
    config.set("configuration", "username", "your-slack-username")
    config.add_section("connection")
    config.set("connection", "url",
               "<insert URL from https://my.slack.com/services/new/incoming-webhook>")
    config.add_section("apply_notifications")
    config.set("apply_notifications", "enabled", "yes")
    config.set("apply_notifications", "allow_groups", "all")
    config.set("apply_notifications", "deny_groups", "local")
    with open(path, 'wb') as f:
        config.write(f)


def _get_config(repo_path):
    config_path = join(repo_path, ".slack.cfg")
    if not exists(config_path):
        _create_config(config_path)
    config = SafeConfigParser()
    config.read(config_path)
    if config.get("configuration", "enabled") == "unconfigured":
        io.stderr("Slack notifications not configured. Please edit .slack.cfg "
                  "(it has already been created) and set enabled to 'yes' "
                  "(or 'no' to silence this message and disable Slack notifications).")
        return None
    elif config.get("configuration", "enabled").lower() not in ("yes", "true", "1"):
        io.debug("Slack notifications not enabled in .slack.cfg, skipping...")
        return None
    elif not REQUESTS:
        io.stderr("Slack notifications need the requests library. "
                  "You can usually install it with `pip install requests`.")
        return None
    return config


def _notify(url, message=None, title=None, fallback=None, user=None, target=None, color="#000000"):
    payload = {
        "icon_url": "http://bundlewrap.org/img/icon.png",
        "username": "bundlewrap",
    }
    if fallback:
        payload["attachments"] = [{
            "color": color,
            "fallback": fallback,
        }]
        if message:
            payload["attachments"][0]["text"] = message
        if title:
            payload["attachments"][0]["title"] = title
        if target and user:
            payload["attachments"][0]["fields"] = [
                {
                    "short": True,
                    "title": "User",
                    "value": user,
                },
                {
                    "short": True,
                    "title": "Target",
                    "value": target,
                },
            ]
    else:
        payload["text"] = message

    try:
        post(
            url,
            headers={
                'content-type': 'application/json',
            },
            data=dumps(payload),
        )
    except ConnectionError as e:
        io.stderr("Failed to submit Slack notification: {}".format(e))


def apply_start(repo, target, nodes, interactive=False, **kwargs):
    config = _get_config(repo.path)
    if config is None or \
            not config.has_section("apply_notifications") or \
            not config.getboolean("apply_notifications", "enabled") or \
            not _check_allowed_groups(config, nodes):
        return
    io.debug("posting apply start notification to Slack")
    _notify(
        config.get("connection", "url"),
        fallback="Starting bw apply to {target} as {user}".format(
            target=target,
            user=config.get("configuration", "username"),
        ),
        target=target,
        title=(
            "Starting {interactive}interactive bw apply..."
        ).format(interactive="non-" if not interactive else ""),
        user=config.get("configuration", "username"),
    )


def apply_end(repo, target, nodes, duration=None, **kwargs):
    config = _get_config(repo.path)
    if config is None or \
            not config.has_section("apply_notifications") or \
            not config.getboolean("apply_notifications", "enabled") or \
            not _check_allowed_groups(config, nodes):
        return
    io.debug("posting apply end notification to Slack")
    _notify(
        config.get("connection", "url"),
        color="good",
        fallback="Finished bw apply to {target} as {user} after {duration}s.".format(
            duration=duration.total_seconds(),
            target=target,
            user=config.get("configuration", "username"),
        ),
        target=target,
        title="Finished bw apply after {}s.".format(duration.total_seconds()),
        user=config.get("configuration", "username"),
    )
