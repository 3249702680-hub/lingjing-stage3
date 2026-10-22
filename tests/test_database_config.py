"""Database authentication configuration checks; no live credentials required."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DatabaseConfigurationTests(unittest.TestCase):
    def run_config(self, code, **variables):
        environment = {k: v for k, v in os.environ.items() if not k.startswith("SQLSERVER_")}
        environment.update(variables)
        environment["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, env=environment,
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_platform_default(self):
        self.run_config(
            "import os; from database import _auth; "
            "assert _auth == ('windows' if os.name == 'nt' else 'sql')"
        )

    def test_sql_auth_never_uses_integrated_auth(self):
        self.run_config(
            "from database import engine; "
            "args, _ = engine.dialect.create_connect_args(engine.url); "
            "assert 'trusted_connection=yes' not in args[0].lower(); "
            "assert 'authentication=sqlpassword' in args[0].lower()",
            SQLSERVER_AUTH="sql",
        )

    def test_missing_sql_credentials_fail_before_connection(self):
        self.run_config(
            "from database import engine; from sqlalchemy.exc import SQLAlchemyError\n"
            "try:\n engine.connect()\n"
            "except SQLAlchemyError as exc:\n"
            " assert 'SQLSERVER_USERNAME' in str(exc)\n"
            "else:\n raise AssertionError('Missing credentials accepted')",
            SQLSERVER_AUTH="sql", SQLSERVER_HOST="example.invalid",
        )

    def test_sql_password_is_escaped_and_url_is_masked(self):
        self.run_config(
            "import os; from database import engine; "
            "args, _ = engine.dialect.create_connect_args(engine.url); "
            "assert 'UID=test_user' in args[0]; "
            "assert 'PWD={synthetic;pass}}word}' in args[0]; "
            "assert os.environ['SQLSERVER_PASSWORD'] not in str(engine.url); "
            "assert 'Server=example.invalid,1433' in args[0]",
            SQLSERVER_AUTH="sql", SQLSERVER_HOST="example.invalid",
            SQLSERVER_PORT="1433", SQLSERVER_USERNAME="test_user",
            SQLSERVER_PASSWORD="synthetic;pass}word",
        )

    def test_invalid_auth_is_rejected(self):
        self.run_config(
            "try:\n import database\n"
            "except ValueError as exc:\n assert 'SQLSERVER_AUTH' in str(exc)\n"
            "else:\n raise AssertionError('Invalid authentication accepted')",
            SQLSERVER_AUTH="invalid",
        )

    def test_explicit_windows_mode(self):
        self.run_config(
            "import os\n"
            "if os.name == 'nt':\n"
            " from database import engine\n"
            " args, _ = engine.dialect.create_connect_args(engine.url)\n"
            " assert 'Trusted_Connection=Yes' in args[0]\n"
            "else:\n"
            " try:\n  import database\n"
            " except ValueError as exc:\n  assert 'only supported on Windows' in str(exc)\n"
            " else:\n  raise AssertionError('Linux Windows auth accepted')",
            SQLSERVER_AUTH="windows",
        )


if __name__ == "__main__":
    unittest.main()
