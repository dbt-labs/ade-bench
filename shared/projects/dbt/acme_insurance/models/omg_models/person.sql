select
    Person_Identifier,
    First_Name,
    Middle_Name,
    Last_Name,
    Full_Legal_Name,
    Nickname,
    Suffix_Name,
    Birth_Date,
    Birth_Place_Name,
    Gender_Code,
    Prefix_Name
from {{ ref('Person') }}