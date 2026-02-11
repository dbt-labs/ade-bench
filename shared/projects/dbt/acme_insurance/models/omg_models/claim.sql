select
    Claim_Identifier,
    Catastrophe_Identifier,
    Claim_Description,
    Claims_Made_Date,
    Company_Claim_Number,
    Company_Subclaim_Number,
    Insurable_Object_Identifier,
    Occurrence_Identifier,
    Entry_Into_Claims_Made_Program_Date,
    Claim_Open_Date,
    Claim_Close_Date,
    Claim_Reopen_Date,
    Claim_Status_Code,
    Claim_Reported_Date
from 
    {{ ref('Claim') }}
