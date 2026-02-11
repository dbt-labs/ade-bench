select
    Claim_Amount_Identifier
from 
    {{ ref('Expense_Payment') }}
