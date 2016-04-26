import base64
import hashlib
import hmac
from os.path import dirname, join
from pipes import quote
from string import ascii_letters, punctuation, digits
from subprocess import CalledProcessError, check_output
from sys import platform

from bundlewrap.utils import get_file_contents


DATA_DIR = join(dirname(dirname(__file__)), "data")
SECRET_FILENAME = "pwget.secret"


def _ensure_secret(path):
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
                ]).strip().decode('utf-8')
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
    if secret.strip() == "dummy":
        return None
    return secret


def _get_fernet_key(dummy_allowed=True):
    secret = _ensure_secret(dirname(dirname(__file__)))
    if secret is None:
        if dummy_allowed:
            return None
        else:
            raise ValueError("cannot encrypt with dummy secret")
    return base64.urlsafe_b64encode(base64.b64decode(secret)[:32])


def decrypt(cryptotext):
    """
    Decrypts a given encrypted password.
    """
    fernet_key = _get_fernet_key()
    if fernet_key is None:
        return "dummy"
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError("Unable to import the cryptography library. "
                          "Install using: pip install cryptography")
    f = Fernet(fernet_key)
    return f.decrypt(cryptotext.encode('utf-8')).decode('utf-8')


def decrypt_file(source_path):
    """
    Decrypts the file at source_path (relative to data/) and
    returns the plaintext as bytes.
    """
    fernet_key = _get_fernet_key()
    if fernet_key is None:
        return b"dummy\n"
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError("Unable to import the cryptography library. "
                          "Install using: pip install cryptography")
    f = Fernet(fernet_key)
    return f.decrypt(get_file_contents(join(DATA_DIR, source_path)))


def encrypt(plaintext):
    """
    Encrypts a given plaintext password and returns a string that can
    be fed into decrypt() to get the password back.
    """
    fernet_key = _get_fernet_key(dummy_allowed=False)
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError("Unable to import the cryptography library. "
                          "Install using: pip install cryptography")
    f = Fernet(fernet_key)
    return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')


def encrypt_file(source_path, target_path):
    """
    Encrypts the file at source_path and places the result at
    target_path. The source_path is relative to CWD or absolute, while
    target_path is relative to data/.
    """
    plaintext = get_file_contents(source_path)
    fernet_key = _get_fernet_key(dummy_allowed=False)
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError("Unable to import the cryptography library. "
                          "Install using: pip install cryptography")
    fernet = Fernet(fernet_key)
    target_file = join(DATA_DIR, target_path)
    with open(target_file, 'wb') as f:
        f.write(fernet.encrypt(plaintext))
    return target_file


def get(identifier, length=32, symbols=False):
    """
    Derives a password from the given identifier and the shared secret
    in the repository.

    This is done by seeding a random generator with an SHA512 HMAC built
    from the secret and the given identifier.

    One could just use the HMAC digest itself as a password, but the
    PRNG allows for more control over password length and complexity.
    """
    secret = _ensure_secret(dirname(dirname(__file__)))
    if secret is None:
        return "dummy"

    alphabet = ascii_letters + digits
    if symbols:
        alphabet += punctuation

    h = hmac.new(secret.encode('utf-8'), digestmod=hashlib.sha512)
    h.update(identifier.encode('utf-8'))
    prng = random(h.digest())
    return "".join([alphabet[next(prng) % (len(alphabet) - 1)] for i in range(length)])


def random(seed):
    """
    Provides a way to get repeatable random numbers from the given seed.

    Unlike random.seed(), this approach provides consistent results
    across platforms.

    See also http://stackoverflow.com/a/18992474
    """
    while True:
        seed = hashlib.sha512(seed).digest()
        for character in seed:
            try:
                yield ord(character)
            except TypeError:  # Python 3
                yield character
