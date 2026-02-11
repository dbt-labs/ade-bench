select  
    Party_Identifier,
    Party_Name,
    Begin_Date,
    End_Date,
    Party_Type_Code
from {{ ref('Party') }}