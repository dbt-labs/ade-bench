select
    Organization_Identifier,
    Industry_Code,
    Organization_Name,
    Dun_And_Bradstreet_Identifier,
    Organization_Type_Code,
    Alternate_Name,
    Organization_Description,
    Acronym_Name,
    Industry_Type_Code
from {{ source('acme_raw', 'Organization') }}