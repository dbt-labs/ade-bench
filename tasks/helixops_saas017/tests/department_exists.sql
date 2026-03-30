select 1 from {{ ref('int_workspace_roster') }} where department is not null limit 0
