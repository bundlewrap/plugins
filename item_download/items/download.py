from bundlewrap.items import Item, ItemStatus
from bundlewrap.exceptions import BundleError
from bundlewrap.utils.text import force_text, mark_for_translation as _
from bundlewrap.utils.remote import PathInfo
import types
from pipes import quote


class Download(Item):
    """
    Download a file and verify its Hash.
    """
    BUNDLE_ATTRIBUTE_NAME = "downloads"
    NEEDS_STATIC = [
        "pkg_apt:",
        "pkg_pacman:",
        "pkg_yum:",
        "pkg_zypper:",
    ]
    ITEM_ATTRIBUTES = {
        'url': {},
        'sha256': {},
    }
    ITEM_TYPE_NAME = "download"
    REQUIRED_ATTRIBUTES = []

    def __repr__(self):
        return "<Download name:{}>".format(self.name)

    def __hash_remote_file(self, filename):
        path_info = PathInfo(self.node, filename)
        if not path_info.is_file:
            return None

        if hasattr(path_info, 'sha256'):
            return path_info.sha256
        else:
            """"pending pr so do it manualy"""
            if self.node.os == 'macos':
                result = self.node.run("shasum -a 256 -- {}".format(quote(filename)))
            elif self.node.os in self.node.OS_FAMILY_BSD:
                result = self.node.run("sha256 -q -- {}".format(quote(filename)))
            else:
                result = self.node.run("sha256sum -- {}".format(quote(filename)))
            return force_text(result.stdout).strip().split()[0]

    def fix(self, status):
        if status.must_be_deleted:
            # Not possible
            pass
        else:
            # download file
            self.node.run("curl -L -s -o {} -- {}".format(quote(self.name), quote(self.attributes.get('url'))))

            # check hash
            sha256 = self.__hash_remote_file(self.name)

            if sha256 != self.attributes.get('sha256'):
                # unlink file
                self.node.run("rm -rf -- {}".format(quote(self.name)))

                return False

    def cdict(self):
        """This is how the world should be"""
        cdict = {
            'type': 'download',
            'sha256': self.attributes.get('sha256'),
        }

        return cdict

    def sdict(self):
        """This is how the world is right now"""
        path_info = PathInfo(self.node, self.name)
        if not path_info.exists:
            return None
        else:
            sdict = {
                'type': 'download',
                'sha256': self.__hash_remote_file(self.name)
            }

        return sdict

    @classmethod
    def validate_attributes(cls, bundle, item_id, attributes):
        if not attributes.get('sha256', None):
            raise BundleError(_(
                "at least one hash must be set on {item} in bundle '{bundle}'"
            ).format(
                bundle=bundle.name,
                item=item_id,
            ))

        if not attributes.get('url', None):
            raise BundleError(_(
                "you need to specify the url on {item} in bundle '{bundle}'"
            ).format(
                bundle=bundle.name,
                item=item_id,
            ))

    def get_auto_deps(self, items):
        deps = []
        for item in items:
            # debian TODO: add other package manager
            if item.ITEM_TYPE_NAME == 'pkg_apt' and item.name == 'curl':
                deps.append(item.id)
        return deps
