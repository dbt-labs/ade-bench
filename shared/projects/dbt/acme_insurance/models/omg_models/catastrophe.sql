select
    Catastrophe_Identifier,
    Catastrophe_Type_Code,
    Catastrophe_Name,
    Industry_Catastrophe_Code,
    Company_Catastrophe_Code
from {{ source('acme_raw', 'Catastrophe') }}