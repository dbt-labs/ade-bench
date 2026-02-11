select
    Physical_Location_Identifier,
    Physical_Location_Name,
    Latitude_Value,
    Longitude_Value,
    Altitude_Value,
    Altitude_Mean_Sea_Level_Value,
    Horizontal_Accuracy_Value,
    Vertical_Accuracy_Value,
    Travel_Direction_Description,
    Location_Address_Identifier
from {{ ref('Physical_Location') }}