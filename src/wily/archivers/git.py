"""
Git Archiver.

Implementation of the archiver API for the gitpython module.
"""
import logging
import posixpath
import stat
import sys
from io import BytesIO
from typing import Dict, List, Tuple

import git.exc
from dulwich.diff_tree import tree_changes
from dulwich.objects import Commit
from dulwich.index import build_index_from_tree
from dulwich.objectspec import parse_tree
from dulwich.porcelain import open_repo_closing
from dulwich.repo import Repo as DRepo
from dulwich.walk import WalkEntry
from git.repo import Repo

from wily.archivers import BaseArchiver, Revision

logger = logging.getLogger(__name__)


class InvalidGitRepositoryError(Exception):
    """Error for when a folder is not a git repo."""

    pass


class DirtyGitRepositoryError(Exception):
    """Error for a dirty git repository (untracked files)."""

    def __init__(self, untracked_files):
        """
        Raise error for untracked files.

        :param untracked_files: List of untracked files
        :param untracked_files: ``list``
        """
        self.untracked_files = untracked_files
        self.message = "Dirty repository, make sure you commit/stash files first"


def ls_tree(
    repo,
    treeish=b"HEAD",
    outstream=sys.stdout,
    recursive=False,
    name_only=False,
    dir_only=False,
):
    """List contents of a tree.

    Args:
      repo: Path to the repository
      treeish: Tree id to list
      outstream: Output stream (defaults to stdout)
      recursive: Whether to recursively list files
      name_only: Only print item name
    """

    def list_tree(store, treeid, base):
        # if isinstance(store[treeid], Commit):
        #     return
        # print(type(store[treeid]), store[treeid])
        for (name, mode, sha) in store[treeid].iteritems():
            a_dir = stat.S_ISDIR(mode)
            if base:
                name = posixpath.join(base, name)
            if name_only and not a_dir and not dir_only:
                outstream.write(name + b"\n")
            elif a_dir and dir_only:
                outstream.write(name + b"\n")
            # else:
            #     outstream.write(pretty_format_tree_entry(name, mode, sha))
            if a_dir and recursive:
                list_tree(store, sha, name)

    with open_repo_closing(repo) as r:
        tree = parse_tree(r, treeish)
        list_tree(r.object_store, tree.id, "")


def checkout(repo, revision=b"HEAD"):
    indexfile = repo.index_path()
    # we want to checkout HEAD
    tree = repo[revision].tree
    build_index_from_tree(repo.path, indexfile, repo.object_store, tree)


def get_tracked_files_dirs(repo: DRepo, hexsha: str) -> Tuple[List[str], List[str]]:
    """Get tracked files in a repo for a commit hash using ls-tree."""
    output = BytesIO()
    ls_tree(repo, hexsha, outstream=output, recursive=True, name_only=True)
    dpaths = output.getvalue().decode().split("\n")
    dpaths.remove("")
    dir_output = BytesIO()
    ls_tree(repo, hexsha, outstream=dir_output, recursive=True, name_only=True, dir_only=True)
    ddirs = dir_output.getvalue().decode().split("\n") + [""]
    return dpaths, ddirs


def whatchanged(
    tree_a: str, tree_b: str, store
) -> Tuple[List[str], List[str], List[str]]:
    """Get files added, modified and deleted between commits."""
    ddiffs = tree_changes(store, tree_b, tree_a)
    dadded_files = []
    dmodified_files = []
    ddeleted_files = []

    for ddiff in ddiffs:
        if ddiff.type == "modify":
            dmodified_files.append(ddiff.new.path.decode())
        elif ddiff.type == "add":
            dadded_files.append(ddiff.new.path.decode())
        elif ddiff.type == "delete":
            ddeleted_files.append(ddiff.old.path.decode())
        elif ddiff.type == "renamed":
            dadded_files.append(ddiff.new.path)
            ddeleted_files.append(ddiff.old.path)
    return dadded_files, dmodified_files, ddeleted_files


class GitArchiver(BaseArchiver):
    """Gitpython implementation of the base archiver."""

    name = "git"

    def __init__(self, config):
        """
        Instantiate a new Git Archiver.

        :param config: The wily configuration
        :type  config: :class:`wily.config.WilyConfig`
        """
        try:
            self.repo = Repo(config.path)
        except git.exc.InvalidGitRepositoryError as e:
            raise InvalidGitRepositoryError from e
        self.drepo = DRepo(config.path)

        self.config = config
        if self.repo.head.is_detached:
            self.current_branch = self.repo.head.object.hexsha
        else:
            self.current_branch = self.repo.active_branch
        assert not self.repo.bare, "Not a Git repository"

    def revisions(self, path: str, max_revisions: int) -> List[Revision]:
        """
        Get the list of revisions.

        :param path: the path to target.
        :type  path: ``str``

        :param max_revisions: the maximum number of revisions.
        :type  max_revisions: ``int``

        :return: A list of revisions.
        :rtype: ``list`` of :class:`Revision`
        """
        if self.repo.is_dirty():
            raise DirtyGitRepositoryError(self.repo.untracked_files)

        revisions = []
        entry: WalkEntry
        dcommit: Commit

        for entry in self.drepo.get_walker(max_entries=max_revisions, reverse=True):
            dcommit: Commit = entry.commit
            tracked_files, tracked_dirs = get_tracked_files_dirs(self.drepo, dcommit.id)
            if not dcommit.parents or not revisions:
                added_files = tracked_files
                modified_files = []
                deleted_files = []
            else:
                added_files, modified_files, deleted_files = whatchanged(
                    dcommit.tree, self.drepo.object_store[dcommit.parents[0]].tree, self.drepo.object_store
                )

            name = dcommit.id.decode()
            logger.debug(f"For revision {name} found:")
            logger.debug(f"Tracked files: {tracked_files}")
            logger.debug(f"Tracked directories: {tracked_dirs}")
            logger.debug(f"Added files: {added_files}")
            logger.debug(f"Modified files: {modified_files}")
            logger.debug(f"Deleted files: {deleted_files}")

            rev = Revision(
                key=name,
                author_name=dcommit.author.decode().split(" ")[0],
                author_email=dcommit.author.decode().split(" ")[1].strip("<>"),
                date=dcommit.commit_time,
                message=dcommit.message.decode(),
                tracked_files=tracked_files,
                tracked_dirs=tracked_dirs,
                added_files=added_files,
                modified_files=modified_files,
                deleted_files=deleted_files,
            )
            revisions.append(rev)
        return revisions[::-1]

    def checkout(self, revision: Revision, options: Dict):
        """
        Checkout a specific revision.

        :param revision: The revision identifier.
        :type  revision: :class:`Revision`

        :param options: Any additional options.
        :type  options: ``dict``
        """
        rev = revision.key.encode()
        # self.repo.git.checkout(rev)
        checkout(self.drepo, rev)

    def finish(self):
        """
        Clean up any state if processing completed/failed.

        For git, will checkout HEAD on the original branch when finishing
        """
        checkout(self.drepo)
        self.repo.close()

    def find(self, search: str) -> Revision:
        """
        Search a string and return a single revision.

        :param search: The search term.
        :type  search: ``str``

        :return: An instance of revision.
        :rtype: Instance of :class:`Revision`
        """
        commit = self.repo.commit(search)
        tracked_files, tracked_dirs = get_tracked_files_dirs(self.drepo, commit.hexsha)
        if not commit.parents:
            added_files = tracked_files
            modified_files = []
            deleted_files = []
        else:
            added_files, modified_files, deleted_files = whatchanged(
                commit.tree.hexsha, self.repo.commit(commit.hexsha + "~1").tree.hexsha, self.drepo.object_store
            )

        return Revision(
            key=commit.name_rev.split(" ")[0],
            author_name=commit.author.name,
            author_email=commit.author.email,
            date=commit.committed_date,
            message=commit.message,
            tracked_files=tracked_files,
            tracked_dirs=tracked_dirs,
            added_files=added_files,
            modified_files=modified_files,
            deleted_files=deleted_files,
        )
