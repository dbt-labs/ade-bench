select
    Claim_Identifier,
    Effective_Date,
    Policy_Coverage_Detail_Identifier
from {{ source('acme_raw', 'Claim_Coverage') }}
