select  
    Insurable_Object_Identifier,
    Geographic_Location_Identifier,
    Insurable_Object_Type_Code
from {{ ref('Insurable_Object') }}
