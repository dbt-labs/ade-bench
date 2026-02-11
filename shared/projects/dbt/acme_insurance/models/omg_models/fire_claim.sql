select
    PolicyNo,
    ClaimNumber,
    Premium,
    InsuredLocation,
    Loss_Ratio,
    Nearest_Firestation_miles,
    Number_of_Firefighters,
    Fireplace,
    Year_Built
from {{ ref('FireClaim') }}