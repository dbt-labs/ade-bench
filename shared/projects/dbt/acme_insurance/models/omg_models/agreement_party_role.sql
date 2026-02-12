select
    Agreement_Identifier,
    Party_Identifier,
    Party_Role_Code,
    Effective_Date,
    Expiration_Date
from 
    {{ source('acme_raw', 'Agreement_Party_Role') }}