select
    Assessment_Result_Identifier,
    Assessment_Identifier,
    Assessment_Result_Type_Code
from 
    {{ ref('Assessment_Result') }}