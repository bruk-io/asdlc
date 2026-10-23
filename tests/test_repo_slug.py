import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import load

slugs = load("scripts/repo_slug.py")

ISOLATED = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class RepoSlugTest(unittest.TestCase):
    def test_every_remote_form_gives_owner_repo(self) -> None:
        cases = {
            "git@github.com:Acme/Web-App.git": "acme-web-app",
            "git@github.com:acme/web-app": "acme-web-app",
            "https://github.com/acme/web-app.git": "acme-web-app",
            "https://github.com/Acme/Web-App": "acme-web-app",
            "https://github.com/acme/web-app/": "acme-web-app",
            "https://user:token@github.com/acme/web-app.git": "acme-web-app",
            "ssh://git@github.com/acme/web-app.git": "acme-web-app",
            "ssh://git@github.com:22/acme/web-app.git": "acme-web-app",
            "git://example.com/acme/web-app.git": "acme-web-app",
            "file:///srv/git/acme/web-app.git": "acme-web-app",
            "/srv/git/acme/web-app.git": "acme-web-app",
            "../acme/web-app.git": "acme-web-app",
            "  git@github.com:acme/web-app.git\n": "acme-web-app",
        }
        for remote, expected in cases.items():
            with self.subTest(remote=remote):
                self.assertEqual(slugs.repo_slug(remote), expected)

    def test_anything_but_letters_and_digits_becomes_one_hyphen(self) -> None:
        self.assertEqual(slugs.repo_slug("git@github.com:Acme_Co/web.app__v2.git"), "acme-co-web-app-v2")
        self.assertEqual(slugs.repo_slug("https://github.com/bruk-io/bruk.io"), "bruk-io-bruk-io")

    def test_a_group_above_the_owner_is_dropped(self) -> None:
        self.assertEqual(slugs.repo_slug("git@gitlab.com:group/sub/repo.git"), "sub-repo")

    def test_no_owner_and_repository_is_no_slug(self) -> None:
        for remote in ("", "https://github.com/repo", "git@github.com:repo.git", "repo.git", "https://github.com/"):
            with self.subTest(remote=remote):
                self.assertIsNone(slugs.repo_slug(remote))


class SlugOfTest(unittest.TestCase):
    def test_reads_origin_from_a_real_repository(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, env=ISOLATED)
            self.assertIsNone(slugs.slug_of(repo))
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:Acme/App.git"], check=True, env=ISOLATED)
            self.assertEqual(slugs.slug_of(repo), "acme-app")

    def test_not_a_repository_is_no_slug(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(slugs.slug_of(Path(folder)))


if __name__ == "__main__":
    unittest.main()
