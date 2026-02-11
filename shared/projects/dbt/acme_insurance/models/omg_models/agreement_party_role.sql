select
    Agreement_Identifier,
    Party_Identifier,
    Party_Role_Code,
    Effective_Date,
    Expiration_Date
from 
    {{ ref('Agreement_Party_Role') }}