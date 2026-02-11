select
    Party_Identifier,
    Assessment_Identifier,
    Party_Role_Code,
    Begin_Date,
    End_Date
from {{ ref('Assesment_Party_Role') }}
