select
    Assessment_Result_Identifier
from {{ ref('Underwriting_Assessment') }}
