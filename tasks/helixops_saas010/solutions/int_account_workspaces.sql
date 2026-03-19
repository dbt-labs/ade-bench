with workspaces as (
    select * from {{ ref('stg_workspaces') }}
)
select
    account_id,
    count(*) as workspace_count,
    sum(case when workspace_status = 'active' then 1 else 0 end) as active_workspace_count,
    sum(case when environment_tier = 'prod' then 1 else 0 end) as prod_workspace_count,
    sum(case when environment_tier = 'sandbox' then 1 else 0 end) as sandbox_workspace_count,
    sum(case when is_primary then 1 else 0 end) as primary_workspace_count,
    max(case when is_primary then workspace_name end) as primary_workspace_name,
    min(created_at) as first_workspace_created_at,
    max(created_at) as latest_workspace_created_at
from workspaces
where workspace_status != 'archived'
group by 1
