# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from atexit import register as at_exit
from os import remove
from os.path import isfile, join
from pipes import quote
from shutil import rmtree
from subprocess import PIPE, Popen
from tempfile import mkdtemp, NamedTemporaryFile

from bundlewrap.exceptions import RepositoryError
from bundlewrap.items import Item
from bundlewrap.utils import cached_property
from bundlewrap.utils.text import mark_for_translation as _, randstr
from bundlewrap.utils.ui import io


REPO_MAP_FILENAME = "git_deploy_repos"
REMOTE_STATE_FILENAME = ".bundlewrap_git_deploy"


def is_ref(rev):
    """
    Braindead check to see if our rev is a branch or tag name. False
    negatives are OK since this is only used for optimization.
    """
    for char in rev:
        if char not in "0123456789abcdef":
            return True
    return False


def clone_to_dir(remote_url, rev):
    """
    Clones the given URL to a temporary directory, using a shallow clone
    if the given revision is definitely not a commit hash.

    Returns the path to the directory.
    """
    tmpdir = mkdtemp()
    if is_ref(rev):
        git_cmdline = ["clone", "--bare", "--depth", "1", "--no-single-branch", remote_url, "."]
    else:
        git_cmdline = ["clone", "--bare", remote_url, "."]
    git_command(git_cmdline, tmpdir)
    return tmpdir


def get_local_repo_path(bw_repo_path, repo_name):
    """
    From the given BundleWrap repo, get the filesystem path to the git
    repo associated with the given internal repo name.
    """
    repo_map_path = join(bw_repo_path, REPO_MAP_FILENAME)
    if not isfile(repo_map_path):
        io.stderr(_("missing repo map for git_deploy at {}").format(repo_map_path))
        io.stderr(_("you must create this file with the following format:"))
        io.stderr(_("  <value of repo attribute on git_deploy item>: "
                    "<absolute path to local git repo>"))
        io.stderr(_("since the path is local, you should also add the "
                    "{} file to your gitignore").format(REPO_MAP_FILENAME))
        raise RepositoryError(_("missing repo map for git_deploy"))

    with open(join(bw_repo_path, REPO_MAP_FILENAME)) as f:
        repo_map = f.readlines()

    for line in repo_map:
        if not line.strip() or line.startswith("#"):
            continue
        try:
            repo, path = line.split(":", 1)
        except:
            raise RepositoryError(_("unable to parse line from {path}: '{line}'").format(
                line=line,
                path=repo_map_path,
            ))
        if repo_name == repo:
            return path.strip()

    raise RepositoryError(_("no path found for repo '{repo}' in {path}").format(
        path=repo_map_path,
        repo=repo_name,
    ))


def git_command(cmdline, repo_dir):
    """
    Runs the given git command line in the given directory.

    Returns stdout of the command.
    """
    cmdline = ["git"] + cmdline
    io.debug(_("running '{}' in {}").format(
        " ".join(cmdline),
        repo_dir,
    ))
    git_process = Popen(
        cmdline,
        cwd=repo_dir,
        stderr=PIPE,
        stdout=PIPE,
    )
    stdout, stderr = git_process.communicate()
    if git_process.returncode != 0:
        io.stderr(_("failed command: {}").format(" ".join(cmdline)))
        io.stderr(_("stdout:\n{}").format(stdout))
        io.stderr(_("stderr:\n{}").format(stderr))
        raise RuntimeError(_("`git {command}` failed in {dir}").format(
            command=cmdline[1],
            dir=repo_dir,
        ))
    return stdout.decode('utf-8').strip()


class GitDeploy(Item):
    """
    Facilitates deployment of a given rev from a local git repo to a
    node.
    """
    BUNDLE_ATTRIBUTE_NAME = "git_deploy"
    ITEM_ATTRIBUTES = {
        'repo': None,
        'rev': None,
        'use_xattrs': False,
    }
    ITEM_TYPE_NAME = "git_deploy"
    REQUIRED_ATTRIBUTES = ['repo', 'rev']

    def __repr__(self):
        return "<GitDeploy path:{} repo:{} rev:{}>".format(
            self.name,
            self.attributes['repo'],
            self.attributes['rev'],
        )

    @cached_property
    def _expanded_rev(self):
        git_cmdline = ["rev-parse", self.attributes['rev']]
        return git_command(
            git_cmdline,
            self._repo_dir,
        )

    @cached_property
    def _repo_dir(self):
        if "://" in self.attributes['repo']:
            repo_dir = clone_to_dir(self.attributes['repo'], self.attributes['rev'])
            io.debug(_("registering {} for deletion on exit").format(repo_dir))
            at_exit(rmtree, repo_dir)
        else:
            repo_dir = get_local_repo_path(self.node.repo.path, self.attributes['repo'])
        return repo_dir

    def cdict(self):
        return {'rev': self._expanded_rev}

    def fix(self, status):
        archive_local = NamedTemporaryFile(delete=False)
        try:
            archive_local.close()
            git_command(
                ["archive", "-o", archive_local.name, self._expanded_rev],
                self._repo_dir,
            )
            temp_filename = ".bundlewrap_tmp_git_deploy_" + randstr()

            try:
                self.node.upload(
                    archive_local.name,
                    temp_filename,
                )
                self.node.run("find {} -mindepth 1 -delete".format(quote(self.name)))
                self.node.run("tar -xf {} -C {}".format(temp_filename, quote(self.name)))
                if self.attributes['use_xattrs']:
                    self.node.run("attr -q -s bw_git_deploy_rev -V {} {}".format(
                        self._expanded_rev,
                        quote(self.name),
                    ))
                else:
                    self.node.run("echo {} > {}".format(
                        self._expanded_rev,
                        quote(join(self.name, REMOTE_STATE_FILENAME)),
                    ))
                    self.node.run("chmod 400 {}".format(
                        quote(join(self.name, REMOTE_STATE_FILENAME)),
                    ))
            finally:
                self.node.run("rm -f {}".format(temp_filename))
        finally:
            remove(archive_local.name)

    def sdict(self):
        if self.attributes['use_xattrs']:
            status_result = self.node.run(
                "attr -q -g bw_git_deploy_rev {}".format(quote(self.name)),
                may_fail=True,
            )
        else:
            status_result = self.node.run(
                "cat {}".format(quote(join(self.name, REMOTE_STATE_FILENAME))),
                may_fail=True,
            )
        if status_result.return_code != 0:
            return {}
        else:
            return {'rev': status_result.stdout.decode('utf-8').strip()}
