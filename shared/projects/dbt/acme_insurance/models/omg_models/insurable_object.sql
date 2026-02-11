select  
    Insurable_Object_Identifier,
    Geographic_Location_Identifier,
    Insurable_Object_Type_Code
from {{ source('acme_raw', 'Insurable_Object') }}
