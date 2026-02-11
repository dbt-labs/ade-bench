select
    Policy_Amount_Identifier,
    Geographic_Location_Identifier,
    Policy_Identifier,
    Effective_Date,
    Amount_Type_Code,
    Earning_Begin_Date,
    Earning_End_Date,
    Policy_Coverage_Detail_Identifier,
    Policy_Amount,
    Insurable_Object_Identifier,
    Insurance_Type_Code
from {{ source('acme_raw', 'Policy_Amount') }}