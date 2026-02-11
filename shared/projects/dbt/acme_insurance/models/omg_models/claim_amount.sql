select
    Claim_Amount_Identifier,
    Claim_Identifier,
    Claim_Offer_Identifier,
    Amount_Type_Code,
    Event_Date,
    Claim_Amount,
    Insurance_Type_Code
from 
    {{ ref('Claim_Amount') }}