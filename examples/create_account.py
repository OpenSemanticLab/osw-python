"""
Combining osw express with example from mediawiki docs:
https://www.mediawiki.org/wiki/API:Account_creation
"""

import json
from pathlib import Path
from typing import List, Optional, Union
from uuid import uuid4

from pydantic.v1 import BaseModel, Field

from osw.express import OswExpress


def create_password_from_uuid() -> str:
    return str(uuid4())


class UserDetails(BaseModel):
    username: str
    email: str
    password: str = Field(default_factory=create_password_from_uuid)
    first_name: Optional[str]
    surname: Optional[str]


def create_account(
    osw_obj: OswExpress,
    user_details: List[UserDetails],
    email_sender: Optional[str] = None,
    save_results_to: Optional[Union[str, Path]] = None,
):
    if email_sender is None:
        email_sender = "Digital Transformation @ Fraunhofer ISC"
    session = osw_obj.site._site.connection

    wiki_url = f"https://{osw_obj.domain}"
    api_endpoint = wiki_url + "/w/api.php"

    # First step
    # Retrieve account creation token from `tokens` module
    params_0 = {
        "action": "query",
        "meta": "tokens",
        "type": "createaccount",
        "format": "json",
    }

    response_0 = session.get(url=api_endpoint, params=params_0)
    data_0 = response_0.json()

    token = data_0["query"]["tokens"]["createaccounttoken"]

    created_accounts = []
    for ud in user_details:
        # Second step
        # Send a post request with the fetched token and other data (user information,
        # return URL, etc.)  to the API to create an account
        params_1 = {
            "action": "createaccount",
            "createtoken": token,
            "username": ud.username,
            "password": ud.password,
            "retype": ud.password,
            "email": ud.email,
            "createreturnurl": wiki_url,
            "format": "json",
        }

        response_1 = session.post(api_endpoint, data=params_1)
        data_1 = response_1.json()
        print(data_1)

        email_text = f"""Dear {ud.first_name} {ud.surname},

        an account has been created for you on {wiki_url}. Please use the following
        credentials to log in:

        Username: {ud.username}
        Password: {ud.password}
        Email: {ud.email}

        Please change your password after logging in.

        Best regards,
        {email_sender}
        """

        created_accounts.append(
            {
                "params": params_1,
                "response": data_1,
                "user_details": ud.dict(),
                "email_text": email_text,
            }
        )
    if save_results_to is not None:
        if not isinstance(save_results_to, Path):
            save_results_to = Path(save_results_to)
        with open(save_results_to, "w") as f:
            json.dump(created_accounts, f, indent=2, ensure_ascii=False)
    return created_accounts


if __name__ == "__main__":
    oswe = OswExpress(
        # domain="healthbatt.projects01.open-semantic-lab.org",
        domain="wiki-dev.open-semantic-lab.org",
        cred_fp=r"C:\Users\gold\ownCloud\Personal\accounts.pwd.yaml",
    )
