"""Create or update OSW User items from MediaWiki accounts and ORCID.

Usage:
    uv run python examples/user_sync.py --domain llm4eln.semos.dev --dry-run
"""

import dotenv

from osw.express import OswExpress
from osw.tools.user_sync import config_from_args, run_user_sync


def main() -> None:
    dotenv.load_dotenv()
    config = config_from_args()
    osw = OswExpress(domain=config.domain, cred_filepath=config.cred_filepath)
    report = run_user_sync(config, osw=osw)
    print(report.summary())


if __name__ == "__main__":
    main()
