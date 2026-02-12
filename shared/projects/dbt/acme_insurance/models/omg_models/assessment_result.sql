select
    Assessment_Result_Identifier,
    Assessment_Identifier,
    Assessment_Result_Type_Code
from 
    {{ source('acme_raw', 'Assessment_Result') }}