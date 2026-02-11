select
    Agreement_Identifier,
    Assessment_Identifier
from {{ ref('Agreement_Assessment') }}