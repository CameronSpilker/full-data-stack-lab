-- A fully observed week with zero downloads means the package went dark or
-- the extract silently failed. Either way it warrants a look before it ships.

select
    tool_name,
    package_name,
    week_start,
    downloads,
    days_observed

from {{ ref('int_packages_weekly') }}

where not is_partial_week
  and downloads <= 0
