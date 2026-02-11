select
    Policy_Identifier,
    Effective_Date,
    Expiration_Date,
    Policy_Number,
    Status_Code,
    Geographic_Location_Identifier
from {{ ref('Policy') }}