select
    Claim_Amount_Identifier
from {{ ref('Loss_Reserve') }}