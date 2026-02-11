select
    Party_Role_Code,
    Party_Role_Name,
    Party_Role_Description
from {{ ref('Party_Role') }}