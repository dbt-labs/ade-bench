select
Location_Address_Identifier,
Line_1_Address,
Municipality_Name,
Line_2_Address,
Postal_Code,
Country_Code,
State_Code,
Begin_Date,
End_Date
from {{ ref('Location_Address') }}