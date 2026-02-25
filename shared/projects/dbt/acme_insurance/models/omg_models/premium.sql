select
    Policy_Amount_Identifier
from {{ source('acme_raw', 'Premium') }}