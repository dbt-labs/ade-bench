select
    Claim_Identifier,
    Effective_Date,
    Policy_Coverage_Detail_Identifier
from {{ ref('Claim_Coverage') }}
