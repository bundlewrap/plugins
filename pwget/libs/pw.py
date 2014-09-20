import hashlib
import hmac
from os.path import join
from random import Random
from string import ascii_letters, punctuation, digits


SECRET_FILENAME = "pwget.secret"


def ensure_secret(path):
    secret_path = join(path, SECRET_FILENAME)
    try:
        with open(secret_path) as f:
            secret = f.read()
    except IOError:
        raise IOError(
            "Unable to read pwget secret from {path}. "
            "You can create a new one with:\n\n"
            "# dd if=/dev/urandom bs=64 count=1 | base64 > pwget.secret".format(
                path=secret_path,
        ))
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
