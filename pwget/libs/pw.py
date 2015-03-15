import hashlib
import hmac
from os.path import join
from random import Random
from pipes import quote
from string import ascii_letters, punctuation, digits
from subprocess import CalledProcessError, check_output
from sys import platform


SECRET_FILENAME = "pwget.secret"


def ensure_secret(path):
    secret_path = join(path, SECRET_FILENAME)
    try:
        with open(secret_path) as f:
            secret = f.read()
    except IOError:
        if platform == 'darwin':
            try:
                return check_output([
                    "security",
                    "find-generic-password",
                    "-a",
                    "bw_pwget_" + path,
                    "-s",
                    "bundlewrap",
                    "-w",
                ]).strip()
            except CalledProcessError:
                raise IOError(
                    "Unable to read pwget secret from {path} or Mac OS Keychain. "
                    "You can create a new one with:\n\n"
                    "# dd if=/dev/urandom bs=64 count=1 | base64 > pwget.secret\n\n"
                    "or (better)\n\n"
                    "# pwgetsecret=`dd if=/dev/urandom bs=64 count=1 | base64`; "
                    "security add-generic-password -a {account} "
                    "-w $pwgetsecret -s bundlewrap\n\n"
                    "or if your team has already created a secret, paste it into this:\n\n"
                    "# read pwgetsecret; "
                    "security add-generic-password -a {account} "
                    "-w $pwgetsecret -s bundlewrap".format(
                        account=quote("bw_pwget_" + path),
                        path=secret_path,
                    ),
                )
        raise IOError(
            "Unable to read pwget secret from {path}. "
            "You can create a new one with:\n\n"
            "# dd if=/dev/urandom bs=64 count=1 | base64 > pwget.secret".format(
                path=secret_path,
            ),
        )
    return secret


def get(repo, identifier, length=32, symbols=False):
    """
    Derives a password from the given identifier and the shared secret
    in the repository.

    This is done by seeding a random generator with an SHA512 HMAC built
    from the secret and the given identifier.

    One could just use the HMAC digest itself as a password, but the
    PRNG allows for more control over password length and complexity.
    """
    secret = ensure_secret(repo.path)
    h = hmac.new(secret, digestmod=hashlib.sha512)
    h.update(identifier)
    prng = Random()
    prng.seed(h.digest())
    alphabet = ascii_letters + digits
    if symbols:
        alphabet += punctuation
    return "".join([prng.choice(alphabet) for i in range(length)])
