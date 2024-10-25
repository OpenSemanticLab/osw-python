import json
import os
import uuid as uuid_module
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
from pydantic.v1 import BaseModel, Field
from typing_extensions import Dict, List, Optional, Union

import osw.data.import_utility as diu
import osw.model.entity as model
from osw.core import OSW
from osw.express import OswExpress
from osw.utils import util
from osw.wtsite import WtPage

# Constants
USER_NS = uuid_module.UUID(model.User.__fields__["type"].default[0].split("OSW")[-1])
ORGANIZATION_NS = uuid_module.UUID(
    model.Organization.__fields__["type"].default[0].split("OSW")[-1]
)


def is_nan(x):
    isnan = False
    if isinstance(x, str):
        if x.strip() == "":
            isnan = True
        elif x.strip() == "nan":
            isnan = True
    elif np.isnan(x):
        isnan = True
    return isnan


def write_to_excel(excel_fp, df, sheet_name, index=False):
    with pd.ExcelWriter(excel_fp, if_sheet_exists="replace", mode="a") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=index)


def create_redirect(
    username_entity_pair: Dict[str, Union[str, model.User]],
    osw_obj: Union[OswExpress, OSW],
    overwrite: bool = False,
):
    username = username_entity_pair["username"]
    user = username_entity_pair["user"]
    page_name = f"User:{username}"
    if user is not None:
        uuid = user.uuid
        fpt = diu.uuid_to_full_page_title(uuid)
        main_slot_content = f"#REDIRECT [[{fpt}]]"
        wtpage = WtPage(
            wtSite=osw_obj.site,
            title=page_name,
        )
        if not wtpage.exists or overwrite:
            wtpage.create_slot(
                slot_key="main",
                content_model="wikitext",
            )
            wtpage.set_slot_content(
                slot_key="main",
                content=main_slot_content,
            )
            wtpage.edit(
                comment="[bot edit] Created redirect to user page",
            )
            print(f"Redirect created for 'https://{domain}/wiki/{page_name}'")


def create_redirects(
    users_to_import: pd.DataFrame,
    user_entities: List[model.User],
    osw_obj: Union[OswExpress, OSW],
    parallel: bool = True,
    overwrite: bool = False,
):
    """Create redirects for users in the users_to_import DataFrame

    Parameters
    ----------
    users_to_import
    user_entities
    osw_obj
    parallel
    overwrite

    Returns
    -------

    """
    username_entity_pairs = []
    for ii in range(len(users_to_import)):
        row_ = users_to_import.iloc[ii]
        username_ = row_["Full name"]
        found = False
        for uu in user_entities:
            if uu.label[0].text.lower() == username_.lower():
                found = True
                break
        if found:
            username_entity_pairs.append({"username": username_, "user": uu})
            if not is_nan(row_["ORCID"]):
                username_entity_pairs.append({"username": row_["ORCID"], "user": uu})

    if parallel:
        return util.parallelize(
            create_redirect,
            username_entity_pairs,
            osw_obj=osw_obj,
            overwrite=overwrite,
            # flush=True,
        )
    else:
        print(f"Creating {len(username_entity_pairs)} redirects serially ...")
        return [
            create_redirect(pair, osw_obj, overwrite=True)
            for pair in username_entity_pairs
        ]


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
        with open(save_results_to, "w", encoding="utf-8") as f:
            json.dump({"list": created_accounts}, f, indent=2, ensure_ascii=False)
    return created_accounts


if __name__ == "__main__":
    cwd = Path(os.getcwd())
    excel_fp = cwd / "users_to_import.xlsx"
    domain = "wiki-dev.open-semantic-lab.org"

    osw_obj = OswExpress(domain)

    # Read the Excel file
    u2i = pd.read_excel(excel_fp, sheet_name="users")
    """Users to import"""
    o2i = pd.read_excel(excel_fp, sheet_name="organizations")
    """Organizations to import"""

    organizations = []
    for i, row in o2i.iterrows():
        rnd_uuid = uuid_module.uuid4()
        uuid = uuid_module.uuid5(ORGANIZATION_NS, str(rnd_uuid))
        if not is_nan(row["ROR ID"]):
            uuid = uuid_module.uuid5(ORGANIZATION_NS, row["ROR ID"])
        if not is_nan(row["OSW ID"]):
            osw_id = row["OSW ID"]
            uuid = diu.osw_id_to_uuid(osw_id)
        website = []
        if not is_nan(row["Website"]):
            website.append(row["Website"])
        ror_id = None
        if not is_nan(row["ROR ID"]):
            ror_id = row["ROR ID"]

        org = model.Organization(
            label=[
                {
                    "lang": "en",
                    "text": row["Name"],
                },
                {
                    "lang": "en",
                    "text": row["Alternative label"],
                },
            ],
            short_name=[{"lang": "en", "text": row["Short name"]}],
            uuid=uuid,
            ror_id=ror_id,
            website=website,
        )
        osw_id = diu.uuid_to_osw_id(org.uuid)
        fpt = diu.uuid_to_full_page_title(org.uuid)
        url = f"https://{domain}/wiki/{fpt}"
        if not is_nan(row["OSW URL"]):
            assert url == row["OSW URL"]
        else:
            o2i.at[i, "OSW URL"] = url
        if not is_nan(row["OSW ID"]):
            assert osw_id == row["OSW ID"]
        else:
            o2i.at[i, "OSW ID"] = osw_id
        organizations.append(org)

    # Write the processed organizations back to the original excel
    write_to_excel(excel_fp, o2i, "organizations", index=False)

    # todo:
    #  * create uuid for sites from the organization's uuid + "Site" (edge cases:
    #    several sites)
    #  * Get Postal addresses from the organizations
    #  * create sites (Label = Company shortname + City + "Site")

    users = []
    for i, row in u2i.iterrows():
        rnd_uuid = uuid_module.uuid4()
        uuid = uuid_module.uuid5(USER_NS, str(rnd_uuid))
        if is_nan(row["Full name"]):
            if not is_nan(row["First name"]) and not is_nan(row["Last name"]):
                full_name_stripped = (
                    f"{row['First name'].strip()} " f"{row['Last name'].strip()}"
                )
                u2i.at[i, "Full name"] = full_name_stripped
            else:
                raise ValueError(
                    "'Full name' is NaN and 'First name' & 'Last name' are NaN."
                )
        else:
            full_name_stripped = row["Full name"].strip()
            first_name = full_name_stripped.split(" ")[0]
            last_name = full_name_stripped.split(" ")[-1]
        middle_name = None
        if len(full_name_stripped.split(" ")) > 2:
            middle_name = full_name_stripped.split(" ")[1:-1]
        username = full_name_stripped
        roles = None
        organization = None
        organizational_unit = None
        orcid_url = None
        website = None
        email = None
        if not is_nan(row["Email"]):
            email = [address.strip() for address in row["Email"].strip().split(",")]
        if not is_nan(row["First name"]):
            first_name = row["First name"]
        if not is_nan(row["Middle name"]):
            middle_name = row["Middle name"].split(" ")
        if not is_nan(row["Last name"]):
            last_name = row["Last name"]
        if not is_nan(row["ORCID"]):
            orcid = row["ORCID"]
            uuid = uuid_module.uuid5(USER_NS, orcid)
            username = orcid
            orcid_url = orcid
            if "orcid.org" not in orcid:
                orcid_url = f"https://orcid.org/{orcid}"
        if not is_nan(row["Website"]):
            website = row["Website"]
            if not isinstance(website, list):
                website = set([website])
        if not is_nan(row["Username"]):
            username = row["Username"]
        else:
            if not is_nan(row["ORCID"]):
                username = row["ORCID"].split("/")[-1]
        if not is_nan(row["OSW ID"]):
            osw_id = row["OSW ID"]
            uuid = diu.osw_id_to_uuid(osw_id)
        if not is_nan(row["Role"]):
            roles = [role for role in row["Role"].split(", ")]
        if not is_nan(row["Organization"]):
            organization_short_name = row["Organization"]
            organization = [
                next(
                    (
                        diu.uuid_to_full_page_title(org.uuid)
                        for org in organizations
                        if org.short_name[0].text == organization_short_name
                    ),
                    None,
                )
            ]
            organization = [oo for oo in organization if oo is not None]
            if len(organization) == 0:
                organization = None
        if not is_nan(row["Organizational unit"]):
            ou_short_name = row["Organizational unit"]
            organizational_unit = [
                next(
                    (
                        diu.uuid_to_full_page_title(org.uuid)
                        for org in organizations
                        if org.short_name[0].text == ou_short_name
                    ),
                    None,
                )
            ]
            organizational_unit = [
                ouu for ouu in organizational_unit if ouu is not None
            ]
            if len(organizational_unit) == 0:
                organizational_unit = None
        user = model.User(
            label=[
                {
                    "lang": "en",
                    "text": row["Full name"],
                },
            ],
            first_name=first_name,
            middle_name=middle_name,
            surname=last_name,
            username=username,
            organization=organization,
            organizational_unit=organizational_unit,
            uuid=uuid,
            email=email,
            orcid=orcid_url,
            website=website,
            role=roles,
        )
        # todo: set site (located at)
        osw_id = diu.uuid_to_osw_id(user.uuid)
        url = f"https://{domain}/wiki/{diu.uuid_to_full_page_title(user.uuid)}"
        if not is_nan(row["OSW URL"]):
            assert url == row["OSW URL"]
        else:
            u2i.at[i, "OSW URL"] = url
        if not is_nan(row["OSW ID"]):
            assert osw_id == row["OSW ID"]
        else:
            u2i.at[i, "OSW ID"] = osw_id
        u2i.at[i, "Username"] = username
        u2i.at[i, "Full name"] = full_name_stripped
        u2i.at[i, "First name"] = first_name
        if middle_name is not None:
            u2i.at[i, "Middle name"] = " ".join(middle_name)
        u2i.at[i, "Last name"] = last_name
        users.append(user)

    # Write the processed users back to the original excel
    write_to_excel(excel_fp, u2i, "users", index=False)
    # todo:
    #  * set site for the users (located at)

    upload = True
    if upload:
        entities = organizations + users
        params = OSW.StoreEntityParam(
            entities=entities, comment="Imported from Excel", parallel=False
        )
        osw_obj.store_entity(param=params)

    redirect = True
    if redirect:
        create_redirects(
            users_to_import=u2i,
            user_entities=users,
            osw_obj=osw_obj,
            parallel=False,
            overwrite=True,
        )

    create_accounts = True
    if create_accounts:
        user_details = []
        for user in users:
            user_details.append(
                UserDetails(
                    username=user.username,
                    email=list(user.email)[0],
                    first_name=user.first_name,
                    surname=user.surname,
                )
            )
        created_accounts = create_account(
            osw_obj=osw_obj,
            user_details=user_details,
            email_sender="Digital Transformation @ Fraunhofer ISC",
            save_results_to=cwd / "created_accounts.json",
        )

    white_list = ""
    for i, row in u2i.iterrows():
        if not is_nan(row["ORCID"]):
            orcid = row["ORCID"]
            fn = row["First name"]
            ln = row["Last name"]
            white_list += f'"{orcid}",  # {fn} {ln}\n'

# todo:
#  * create user logins (list + ISC)
