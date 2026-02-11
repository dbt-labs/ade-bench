select
    Agreement_Type_Code,
    Agreement_Name,
    Agreement_Original_Inception_Date,
    Product_Identifier
from 
    {{ ref('Agreement') }}
