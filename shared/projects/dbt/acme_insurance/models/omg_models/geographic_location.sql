select
    Geographic_Location_Identifier,
    Parent_Geographic_Location_Identifier,
    Geographic_Location_Type_Code,
    Location_Code,
    Location_Name,
    Location_Number,
    State_Code,
    Location_Address_Identifier,
    Physical_Location_Identifier
from {{ source('acme_raw', 'Geographic_Location') }}