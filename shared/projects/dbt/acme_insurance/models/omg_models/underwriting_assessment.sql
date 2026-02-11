select
    Assessment_Result_Identifier
from {{ source('acme_raw', 'Underwriting_Assessment') }}
