select
    Claim_Amount_Identifier
from 
    {{ source('acme_raw', 'Expense_Payment') }}
