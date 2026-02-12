select
    Agreement_Identifier,
    Assessment_Identifier
from {{ source('acme_raw', 'Agreement_Assessment') }}