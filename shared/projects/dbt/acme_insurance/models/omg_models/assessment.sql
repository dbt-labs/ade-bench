select
    Assessment_Identifier,
    Begin_Date,
    Assessment_Description,
    End_Date,
    Assessment_Reason_Description
from {{ source('acme_raw', 'Assessment') }}